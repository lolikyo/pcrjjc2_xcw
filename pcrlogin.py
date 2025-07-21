import asyncio
from asyncio import Lock
from json import load, loads
from os.path import dirname, join

import hoshino
from hoshino import config as bot_config
from nonebot import get_bot, on_command

from .aiorequests import get
from .jjcbinds import JJCBindsStorage
from .pcrclient import pcrclient, bsdkclient, ApiException
from .service import sv
from .util import send_to_admin

bot = get_bot()
JJCB = JJCBindsStorage()
curpath = dirname(__file__)
try:
    with open(join(curpath, 'account.json')) as fp:
        acinfos = load(fp)
except:
    sv.logger.critical("未找到账号文件！")

admin = hoshino.config.SUPERUSERS[0]

pro_queue = asyncio.PriorityQueue()


async def get_local_address():
    if hasattr(bot_config, "PUBLIC_ADDRESS") and getattr(bot_config, "PUBLIC_ADDRESS"):
        public_address = getattr(bot_config, 'PUBLIC_ADDRESS')
    elif hasattr(bot_config, "IP") and getattr(bot_config, "IP"):
        public_address = f"{getattr(bot_config, 'IP')}:{getattr(bot_config, 'PORT')}"
    else:
        try:
            res = await (await get(url=f"https://4.ipw.cn", timeout=3)).text
            public_address = f"{res}:{getattr(bot_config, 'PORT')}"
        except:
            public_address = f"localhost:{getattr(bot_config, 'PORT')}"
    return public_address


class Login:
    def __init__(self, account_info, client_no):
        self.ac_info = account_info  # 账号信息

        self.captcha_lck = Lock()  # 验证码锁
        self.validate = None  # 验证码或者验证方式信息，与auto,captcha_verifier有关
        self.validating = False  # 验证状态
        self.ac_first = False
        self.auto = True  # 验证方式
        self.captcha_cnt = 0  # 自动过验证码尝试次数

        self.client = pcrclient(bsdkclient(self.ac_info, self.captcha_verifier, self.errlogger))
        self.no = client_no  # 客户端编号
        self.avail = False  # 客户端可用性

        self.login_cnt = 0  # 登陆出错尝试重连次数
        self.login_lock = Lock()  # 登录锁

    async def captcha_verifier(self, *args):
        if len(args) == 0:
            return self.auto
        if len(args) == 1 and type(args[0]) == int:
            self.captcha_cnt = args[0]
            return self.captcha_cnt

        if not self.ac_first:
            await self.captcha_lck.acquire()
            self.ac_first = True

        self.validating = True
        if not self.auto:
            if not admin:
                sv.logger.critical('需要发验证码给主人，但是主人QQ没有设置，无法继续后续流程')
                raise Exception("需要发验证码给主人，但是主人QQ没有设置，无法继续后续流程")
            else:
                gt = args[0]
                challenge = args[1]
                userid = args[2]
                online_url_head = "https://cc004.github.io/geetest/geetest.html"
                url = f"?captcha_type=1&challenge={challenge}&gt={gt}&userid={userid}&gs=1"
                online_url = online_url_head + url
                sv.logger.info(f'来自{self.no}号客户端的验证:{online_url}')
                if bot_config.HOST == '0.0.0.0':
                    public_address = await get_local_address()
                    local_url_head = f"http://{public_address}/geetest"
                    local_url = local_url_head + url
                else:
                    local_url = f"http://localhost:{bot_config.PORT}/geetest" + url
                try:
                    await asyncio.sleep(5)
                    await send_to_admin(
                        f'pcr账号登录需要验证码，请在浏览器中打开链接，'
                        f'将验证内容后将第1个方框的内容点击复制，并加上"pcrval {self.no} "前缀发送(空格必须)给机器人完成验证\n'
                        f'（有公网IP但是无法访问插件自带链接请检查服务器是否开放端口,显示地址为localhost的请在bot运行的计算机上打开）'
                        f'插件自带链接：{local_url}\n'
                        f'备用公共链接：{online_url}\n'
                        f'示例：pcrval {self.no} 123456789\n您也可以发送 pcrval {self.no} auto 命令bot自动过验证码')
                except Exception as e:
                    sv.logger.critical(e)
                await self.captcha_lck.acquire()
                self.validating = False
                return self.validate

        auto_flag = True
        while auto_flag:
            self.captcha_cnt += 1
            try:
                print(f'客户端{self.no}新版自动过码中，当前尝试第{self.captcha_cnt}/3次。')
                gt = args[0]
                challenge = args[1]
                userid = args[2]

                await asyncio.sleep(1)
                url = f"https://pcrd.tencentbot.top/geetest_renew?captcha_type=1&challenge={challenge}&gt={gt}&userid={userid}&gs=1"
                header = {"Content-Type": "application/json", "User-Agent": "pcrjjc2/1.0.0"}
                res = await (await get(url=url, headers=header, timeout=5)).content
                res = loads(res)
                uuid = res["uuid"]
                msg = [f"uuid={uuid}"]

                await asyncio.sleep(10)
                ccnt = 0
                while ccnt < 3:
                    ccnt += 1
                    res = await (
                        await get(url=f"https://pcrd.tencentbot.top/check/{uuid}", headers=header, timeout=5)).content
                    res = loads(res)
                    if "queue_num" in res:
                        nu = res["queue_num"]
                        msg.append(f"queue_num={nu}")
                        tim = min(int(nu), 3) * 10
                        msg.append(f"sleep={tim}")
                        print(f"客户端{self.no}仍在排队等待:\n" + "\n".join(msg))
                        await asyncio.sleep(tim)
                    else:
                        info = res["info"]
                        if info in ["fail", "url invalid"]:
                            break
                        elif info == "in running":
                            await asyncio.sleep(5)
                        elif 'validate' in info:
                            print(f'客户端{self.no}:info={info}')
                            self.validating = False
                            return info
            except Exception as e:
                print(e)
            if self.captcha_cnt >= 3:
                auto_flag = False

        if not auto_flag:
            self.auto = False
            await send_to_admin(f'客户端{self.no}自动过码多次尝试失败，可能为服务器错误，自动切换为手动。\n'
                                f'确实服务器无误后，可发送 pcrval {self.no} auto重新触发自动过码。\n'
                                f'客户端{self.no}切换至手动')
            self.validating = False
            return "manual"

        await self.errlogger("captchaVerifier: uncaught exception")
        self.validating = False
        return False

    async def errlogger(self, msg):
        # if msg == 'geetest or captcha succeed':
        #     msg = "登录成功"
        try:
            await send_to_admin(message=f'账号{self.ac_info["account"]}登录发生错误：{msg}')
        except:
            sv.logger.critical(f'发送pcr账号登录失败信息至管理员失败')

    # 查询玩家信息以及竞技场信息方法
    async def query(self):
        sv.logger.info(f'{self.no}号客户端开始执行查询任务了')
        while True:
            # 需要登录就重新登录
            if self.client.shouldLogin:
                self.avail = False
                await self.login()
                sv.logger.info(f'{self.no}号客户端{self.ac_info["account"]}重新登录成功！')
                self.avail = True

            # 从队列取任务
            try:
                one = await pro_queue.get()
                data = one.data
                method = data[0]
                values = data[1]
                method_name = method.__name__
                game_id = values['game_id']
            except Exception as e:
                sv.logger.error(f'分析队列任务出错:{e}')
                await asyncio.sleep(1)
                continue
            # 开始查询
            try:
                resall = (await self.client.callapi('/profile/get_profile', {
                    'target_viewer_id': int(game_id)
                }))
            except ApiException as e:
                sv.logger.error(f'对{game_id}的检查出错{e}')
                if e.code == 6:
                    JJCB.remove_by_game_id(game_id)
                    sv.logger.critical(f'已经自动删除错误的订阅{game_id}')
                continue
            except Exception as e:
                sv.logger.error(f'对{game_id}的检查出错{e}')
                continue
            if method_name == 'query_rank':
                try:
                    await method(resall, self.no, values['game_id'], values['user_id'], values['ev'], values['n'])
                except Exception as e:
                    sv.logger.critical(e)
            elif method_name == 'query_info':
                try:
                    await method(resall, self.no, values['ev'])
                except Exception as e:
                    sv.logger.critical(e)
            elif method_name == 'compare':
                try:
                    await method(resall, self.no, values['bind_info'])
                except Exception as e:
                    sv.logger.critical(e)
            elif method_name == 'sleep_clean':
                try:
                    await method(resall, values['bind_info'], values['limit_rank'], values['session'])
                except Exception as e:
                    sv.logger.critical(e)
            else:
                continue

    async def login(self):

        exceptions = [None]
        while True:
            await self.login_lock.acquire()
            while self.login_cnt < 3:
                exceptions = await asyncio.gather(self.client.login(), return_exceptions=True)
                # 登录正常
                if exceptions == [None]:
                    self.login_cnt = 0
                    break
                # 登陆异常
                else:
                    self.login_cnt += 1
                    sv.logger.critical(f'客户端{self.no}出错{str(exceptions)}第{self.login_cnt}次，等待5秒重连')
                    try:
                        if exceptions[0].code == 0:
                            sv.logger.info(f'客户端{self.no}更新版本号')
                            self.client.update_version()
                            self.client.set_headers()
                    except:
                        pass
                    await asyncio.sleep(5)

            # 3次登录出错不再自动重试，报告admin
            if self.login_cnt >= 3:
                rep_exc = await asyncio.gather(
                    send_to_admin(message=f'客户端{self.no}出错{str(exceptions)}超过3次,'
                                          f'可能为网络错误，确认网络正常后,发送pcrlogin {self.no}重试'),
                    return_exceptions=True)
                if rep_exc != [None]:
                    sv.logger.critical(f'向管理员报告客户端{self.no}失败信息出错{str(rep_exc)}')
                await self.login_lock.acquire()
                self.login_cnt = 0

            try:
                self.login_lock.release()
            except Exception as e:
                sv.logger.critical(f'{self.no}号客户端登录锁异常{e}')

            if exceptions == [None]:
                break

    async def first_login(self):
        await self.login()
        sv.logger.info(f'{self.no}号客户端{self.ac_info["account"]}首次登录成功！')
        self.avail = True
        # 开始执行查询
        await self.query()


inst_list = []
no = 0
for ac_info in acinfos:
    login_inst = Login(ac_info, no)
    inst_list.append(login_inst)
    sv.logger.info(f'{login_inst.no}号PCR客户端账号{ac_info["account"]}创建了!')
    loop = asyncio.get_event_loop()
    # 创建客户端后即登录
    loop.create_task(login_inst.first_login())
    no += 1


def get_avail():
    avail = False
    for inst in inst_list:
        if inst.avail:
            avail = True
            break
    return avail


# 客户端出错，手动登录
@on_command('pcrlogin')
async def validate(session):
    if session.ctx['user_id'] == admin:
        client_no = session.ctx['message'].extract_plain_text().replace(f"pcrlogin", "").strip()
        sid = session.ctx['self_id']
        try:
            inst = inst_list[int(client_no)]
            try:
                inst.login_lock.release()
                await bot.send_private_msg(self_id=sid, user_id=admin, message=f'客户端{client_no}再次尝试登录')
            except:
                await bot.send_private_msg(self_id=sid, user_id=admin, message=f'客户端{client_no}已经登录')
        except:
            await bot.send_private_msg(self_id=sid, user_id=admin, message=f'不存在客户端{client_no}')


# 查看客户端状态
@on_command('pcrstatus')
async def get_client_info(session):
    if session.ctx['user_id'] == admin:
        client_no = session.ctx['message'].extract_plain_text().replace(f"pcrstatus", "").strip()
        msg_list = []
        sid = session.ctx['self_id']
        # 指定序号查序号客户端
        if client_no:
            try:
                client_no = int(client_no)
                inst = inst_list[client_no]
                msg_list.append(f"客户端{inst.no}:\n"
                                f"账号{inst.ac_info['account']}\n"
                                f"登录方式:{'自动' if inst.auto else '手动'}\n"
                                f"验证码状态:{'卡验证' if inst.validating else '未卡验证'}\n"
                                f"登录状态:{'未登录' if inst.client.shouldLogin else '已登录'}\n"
                                f"可用性:{'可用' if inst.avail else '不可用'}\n"
                                )
                await bot.send_private_msg(self_id=sid,
                                           user_id=admin,
                                           message=f"{''.join(msg_list)}")
            except:
                await bot.send_private_msg(self_id=sid, user_id=admin, message=f'不存在客户端{client_no}')
        # 不指定查全部可用性状态
        else:
            for inst in inst_list:
                msg_list.append(f"客户端{inst.no}:\n"
                                f"账号{inst.ac_info['account']}\n"
                                f"可用性:{'可用' if inst.avail else '不可用'}\n"
                                )
            await bot.send_private_msg(self_id=sid,
                                       user_id=admin,
                                       message=f"{''.join(msg_list)}共{len(inst_list)}个客户端")


# 客户端手动过验证
@on_command('pcrval')
async def validate(session):
    if session.ctx['user_id'] == admin:
        msp = session.ctx['message'].extract_plain_text().replace(f"pcrval", "").strip().split(" ", 1)
        # client_no 账号编号 client_validate 验证码
        client_no = int(msp[0])
        client_validate = msp[1]
        sid = session.ctx['self_id']
        try:
            inst = inst_list[client_no]
            if client_validate == "manual":
                inst.auto = False
                await bot.send_private_msg(self_id=sid, user_id=admin, message=f'客户端{inst.no}切换至手动')
            elif client_validate == "auto":
                inst.auto = True
                await bot.send_private_msg(self_id=sid, user_id=admin, message=f'客户端{inst.no}切换至自动')
            try:
                inst.validate = client_validate
                inst.captcha_lck.release()
            except:
                pass
        except:
            await bot.send_private_msg(self_id=sid, user_id=admin, message=f'不存在客户端{client_no}')
