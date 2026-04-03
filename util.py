import asyncio
import re
import time
from nonebot import get_bot
import hoshino

cqbot = get_bot()


# 获取当前时间
def get_now_localtime():
    now_localtime = time.strftime("%H:%M:%S", time.localtime())
    return now_localtime


# 时间转换
def timechange(timestr):
    timestamp = int(timestr)
    timearray = time.localtime(timestamp)
    otherstyletime = time.strftime("%Y-%m-%d %H:%M:%S", timearray)
    return otherstyletime


def timechange2(timestr):
    timestamp = int(timestr)
    timearray = time.localtime(timestamp)
    otherstyletime = time.strftime("%m-%d %H:%M:%S", timearray)
    return otherstyletime


# 名称获取
async def get_user_name(user_id, group_id):
    flag = False
    for sid in hoshino.get_self_ids():
        try:
            user = await cqbot.get_group_member_info(self_id=int(sid), group_id=group_id, user_id=user_id)
            user_name = user['card'] if user['card'] != '' else user['nickname']
            flag = True
            return str(user_name)
        except:
            pass
    if not flag:
        raise Exception(f'查询用户资料异常')


async def get_group_name(group_id):
    flag = False
    for sid in hoshino.get_self_ids():
        try:
            group = await cqbot.get_group_info(self_id=int(sid), group_id=group_id)
            group_name = group['group_name']
            flag = True
            return str(group_name)
        except:
            pass
    if not flag:
        raise Exception(f'查询群资料异常')


# 发送到管理员
async def send_to_admin(message):
    flag = False
    for sid in hoshino.get_self_ids():
        try:
            await asyncio.wait_for(cqbot.send_private_msg(self_id=int(sid),
                                                          user_id=hoshino.config.SUPERUSERS[0],
                                                          message=message), timeout=15)
            flag = True
            break
        except Exception as e:
            print(e)
    if not flag:
        message = await img_simplify(message)
        raise Exception(f'向管理员发送消息【{message}】出错')


# 发送到群
async def send_to_group(group_id, message):
    flag = False
    for sid in hoshino.get_self_ids():
        try:
            await asyncio.wait_for(cqbot.send_group_msg(self_id=int(sid),
                                                        group_id=group_id,
                                                        message=message), timeout=15)
            flag = True
            break
        except Exception as e:
            print(e)
    if not flag:
        message = await img_simplify(message)
        raise Exception(f'向群{group_id}发送消息【{message}】出错')


# 发送到好友
async def send_to_friend(user_id, message):
    flag = False
    for sid in hoshino.get_self_ids():
        try:
            await asyncio.wait_for(cqbot.send_private_msg(self_id=int(sid),
                                                          user_id=user_id,
                                                          message=message), timeout=15)
            flag = True
            break
        except Exception as e:
            print(e)
    if not flag:
        message = await img_simplify(message)
        raise Exception(f'向用户{user_id}发送消息【{message}】出错')


# 发送给sender
async def send_to_sender(ev, message):
    try:
        await asyncio.wait_for(cqbot.send_group_msg(self_id=ev.self_id,
                                                    group_id=ev.group_id,
                                                    message=f'[CQ:at,qq={ev.user_id}]{message}'), timeout=15)
    except asyncio.TimeoutError:
        message = await img_simplify(message)
        raise Exception(f'bot账号{ev.self_id}向群{ev.group_id}里用户{ev.user_id}发送群消息【{message}】超时')
    except Exception:
        message = await img_simplify(message)
        raise Exception(f'bot账号{ev.self_id}向群{ev.group_id}里用户{ev.user_id}发送群消息【{message}】出错')


async def img_simplify(message):
    pattern = r'\[CQ:image.*?\]'
    message = re.sub(pattern, '图片', message)
    return message


# 获取好友列表
async def get_all_friend_list():
    friend_list = set()
    for sid in hoshino.get_self_ids():
        try:
            fl = await cqbot.get_friend_list(self_id=int(sid))
            for f in fl:
                friend_list.add(f['user_id'])
        except:
            raise Exception(f'{sid}获取好友列表出错')
    return friend_list


# 获取群列表
async def get_all_group_list():
    group_list = set()
    for sid in hoshino.get_self_ids():
        try:
            gl = await cqbot.get_group_list(self_id=int(sid))
            for g in gl:
                group_list.add(g['group_id'])
        except:
            raise Exception(f'{sid}获取群列表出错')
    return group_list


async def send_sv_group(sv, message):
    gl = sv.enable_group
    for g in gl:
        await asyncio.sleep(0.5)
        try:
            await send_to_group(group_id=g, message=message)
            sv.logger.info(f'群{g} 投递bot信息成功')
        except:
            sv.logger.critical(f'群{g} 投递bot信息失败')
