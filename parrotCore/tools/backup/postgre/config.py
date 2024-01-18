#!encoding=utf-8

"""连接数据库信息"""
DB_information = {
    'db_ip': '192.168.x.x',
    'db_user': 'postgres',
    'db_password': 'xxxx',
    'db_database': 'postgres',
    'db_port': 5432
}

# 数据库容器ID
container_id = 'a74ee76ee144'

"""备份目录路径，结尾加 / (必须是已存在的目录)"""
Backup_path = "/home/backup_pgsql/"

"""定时执行的时间"""
# week:星期（0-6；0为周一，6为周日） hour:小时（24小时制） minute:分（如果是05分执行，则写5；00分执行，则写0）
# 举个栗子：week:3 hour:20 minute:5代表：每周四晚上的8点05分执行任务
cron_time = {
    'week': 2,
    'hour': 11,
    'minute': 41
}

"""选择备份的方式：1:单/多模式备份 2:单库备份 3:单/多表备份 4:整库备份 5:多库备份"""
way = '5'

"""1:单/多模式备份"""
# 单个模式写一个，多个递增即可
db_schema = 'shilidb'
schemas = [
    'kfpt_ht',
    'xh_yw'
]

"""3:单/多表备份"""
# 单个表写一个，多个递增即可（格式：模式名.表名）
db_table = 'shilidb'
table_schemas = 'xh_yw'
tables = [
    'qxz_tb',
    'qxz_py'
]

"""2:单库备份，填库名"""
backup_one = 'shilidb'

"""5:多库备份，填库名"""
backup_double = [
    'data',
    'shilidb',
    'postgres'
]

"""执行备份时的缓存时间(单位秒)"""
# 根据库的大小进行调整，库越大，应当将缓存时间调高；最小值建议不低于10;
time_buffer = 10

"""定义删除多少天之前的备份目录"""
del_dirtime = 30

"""发送邮件"""
# username_send:发送人的用户名  password:发送人邮箱的授权码  username_recv:收件人用户名  port:邮箱端口
email_information = {
    'mailserver': 'smtp.163.com',
    'username_send': 'xxxxxxxxxx@163.com',
    'password': 'xxxxxxxxxx',
    'port': 25
}
# username_to:收件人邮箱，多个收件人按照格式递增添加
username_to = [
    'xxxxxxxxx@qq.com',
    'xxxxxxxxx@qq.com',
    'xxxxxxxxx@163.com'
]

"""邮件内容"""
# mail_head:邮件标题  mail_body:邮件内容
email_text = {
    'mail_head': '数据库服务器备份通知',
    'mail_body': '数据库已备份完成'
}