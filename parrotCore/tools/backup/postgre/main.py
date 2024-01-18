#!/usr/bin/python3
# !encoding=utf-8
"""作者：Hezhilin
   更新时间：2022.5.25
   名称：Python定时备份数据库（整库、模式、表多功能备份）
"""
import os
import os.path
import logging
import time
import psycopg2 as pgsql
import traceback
import smtplib
from config import *
from email.mime.text import MIMEText


class DatabaseBR(object):
    """备份、恢复、定时执行的类"""
    Time = time.strftime('%Y-%m-%d %H:%M:%S')
    Dirtime = time.strftime('%Y%m%d%H')
    Dirbackup = 'pg_back_' + Dirtime
    sql = "select datname from pg_database;"

    logging.basicConfig(level=logging.DEBUG, filename=os.path.abspath(os.path.dirname(__file__)) + '/pgbackup.log',
                        format='%(asctime)s - %(funcName)s{} -%(levelname)s : %(message)s'.format("方法"))
    logging.info("检测备份目录是否存在……")
    if os.path.exists(Backup_path):
        if not os.path.exists(Backup_path + Dirbackup):
            logging.warning("正在创建备份目录")
            os.mkdir(Backup_path + Dirbackup)
        else:
            logging.info("备份目录 %s 已存在" % Dirbackup)
    else:
        logging.error("目录 %s 不存在" % Backup_path)

    def conn_pgsql(self):
        '''连接数据库'''
        logging.info("进入连接数据库的方法")
        conn = None
        try:
            conn = pgsql.connect(database=DB_information['db_database'], user=DB_information['db_user'],
                                 password=DB_information['db_password'], host=DB_information['db_ip'],
                                 port=DB_information['db_port'])
            logging.info("连接Postgres:{}".format(conn))
        except Exception as e:
            logging.error("pgsql连接报错\n%s" % traceback.format_exc())
        if conn != None:
            return conn

    def execute_time(func):
        """装饰器：计算函数的执行时间"""
        from time import time
        def wrapper(*args, **kwargs):
            start = time()
            func_return = func(*args, **kwargs)
            end = time()
            logging.warning(f'{func.__name__}方法执行的时间为: {end - start}s')
            return func_return

        return wrapper

    def execute_rmdir(func):
        """装饰器：删除指定日期前的备份目录"""
        import os, datetime, time, shutil
        def rm_daydir(*args, **kwargs):
            all_dir = []
            for f in list(os.listdir(Backup_path)):
                dirs = "{0}{1}".format(Backup_path, f)
                if os.path.isdir(dirs):
                    all_dir.append(dirs)
            for i in range(len(all_dir)):
                dir_createtime = time.strftime("%Y%m%d", time.localtime(os.path.getctime(all_dir[i])))
                del_time = datetime.date.today() - datetime.timedelta(days=del_dirtime)
                del_time_str = del_time.strftime("%Y%m%d")
                if int(dir_createtime) < int(del_time_str):
                    logging.warning("正在删除备份目录……")
                    shutil.rmtree(all_dir[i])
                    logging.info("已删除{}目录".format(all_dir[i]))
            else:
                logging.info("没有检测到符合删除日期的备份目录")
            func(*args, **kwargs)

        return rm_daydir

    @execute_rmdir
    @execute_time
    def backing(self):
        """备份所有库的方法"""
        con_pg = None
        logging.info("进入执行备份所有库的方法")
        logging.info("正在连接数据库……")
        try:
            con_pg = self.conn_pgsql()
            curs = con_pg.cursor()
            curs.execute(self.sql)
            results = curs.fetchall()
            databases = []
            for result in results:
                result = list(result)
                databases.append(result)
            logging.info("当前的可备份的数据库有\n{}".format(databases))
            for database in databases:
                logging.info("开始备份 %s 库" % database[0])
                dumps = "docker exec -i -d {0} /bin/bash -c 'pg_dump -U {1} {2} > /{3}.sql'".format(
                    container_id, DB_information['db_user'], database[0], database[0])
                os.popen(dumps)
                time.sleep(time_buffer)
            for cpsql in databases:
                copy_sql = "docker cp {0}:/{1}.sql '{2}'".format(
                    container_id, cpsql[0], Backup_path + self.Dirbackup + '/')
                logging.warning("开始从容器%s中备份到宿主机" % container_id)
                os.popen(copy_sql)
                time.sleep(time_buffer)
            curs.close()
            logging.warning("提交事务")
            con_pg.commit()
        except Exception as e:
            logging.error("执行备份所有库的方法报错%s" % traceback.format_exc())
        finally:
            con_pg.close()
            logging.info("关闭数据库连接")
            self.emails()

    @execute_rmdir
    @execute_time
    def backup_onedb(self):
        """备份单库的方法"""
        logging.info("进入备份单库的方法")
        con_pg = None
        logging.info("获取到要备份的数据库名称%s" % backup_one)
        logging.info("正在连接数据库……")
        try:
            con_pg = self.conn_pgsql()
            curs = con_pg.cursor()
            curs.execute(self.sql)
            results = curs.fetchall()
            databases = []
            for result in results:
                result = list(result)
                databases.append(result[0])
            if backup_one in databases:
                logging.info("开始备份 %s 库" % backup_one)
                dumps = "docker exec -i -d {0} /bin/bash -c 'pg_dump -U {1} {2} > /{3}.sql'".format(
                    container_id, DB_information['db_user'], backup_one, backup_one)
                os.popen(dumps)
                time.sleep(time_buffer)
                copy_sql = "docker cp {0}:/{1}.sql {2}".format(
                    container_id, backup_one, Backup_path + self.Dirbackup + '/')
                logging.warning("开始从容器%s中备份到宿主机" % container_id)
                os.popen(copy_sql)
            else:
                logging.error("数据库 %s 不存在，请检查后重新运行！" % backup_one)
        except Exception as e:
            logging.error("执行备份单库的方法报错%s" % traceback.format_exc())
        finally:
            con_pg.close()
            logging.info("关闭数据库连接")
            self.emails()

    @execute_rmdir
    @execute_time
    def backup_doubledb(self):
        """备份多个库的方法"""
        con_pg = None
        logging.info("进入备份多个库的方法")
        logging.info("正在连接数据库……")
        try:
            con_pg = self.conn_pgsql()
            curs = con_pg.cursor()
            curs.execute(self.sql)
            results = curs.fetchall()
            database = []
            for result in results:
                result = list(result)
                database.append(result[0])
            for backup_doubles in backup_double:
                if backup_doubles in database:
                    logging.info("开始备份 %s 库" % backup_doubles)
                    dumps = "docker exec -i -d {0} /bin/bash -c 'pg_dump -U {1} {2} > /{3}.sql'".format(
                        container_id, DB_information['db_user'], backup_doubles, backup_doubles)
                    os.popen(dumps)
                    time.sleep(time_buffer)
                    copy_sql = "docker cp {0}:/{1}.sql {2}".format(
                        container_id, backup_doubles, Backup_path + self.Dirbackup + '/')
                    logging.warning("开始从容器%s中备份到宿主机" % container_id)
                    os.popen(copy_sql)
                    time.sleep(time_buffer)
                else:
                    logging.error("数据库 %s 不存在，请检查后重新运行！" % backup_doubles)

        except Exception as e:
            logging.error("执行备份多库方法报错%s" % traceback.format_exc())
        finally:
            con_pg.close()
            logging.info("关闭数据库连接")
            self.emails()

    @execute_rmdir
    @execute_time
    def schemas(self):
        """备份单/多模式的方法"""
        logging.info("进入执行备份单/多模式的方法")
        con_pg = None
        try:
            logging.info("正在连接数据库……")
            con_pg = self.conn_pgsql()
            curs = con_pg.cursor()
            curs.execute(self.sql)
            results = curs.fetchall()
            databases = []
            for result in results:
                result = list(result)
                databases.append(result[0])
            if db_schema in databases:
                logging.info("开始备份 %s 模式" % schemas)
                for schema in schemas:
                    dumps = "docker exec -i -d {0} /bin/bash -c 'pg_dump  -U postgres {1} --schema={2} > /{3}.sql'".format(
                        container_id, db_schema, schema, schema)
                    os.popen(dumps)
                    time.sleep(time_buffer)
                    copy_sql = "docker cp {0}:/{1}.sql {2}".format(
                        container_id, schema, Backup_path + self.Dirbackup + '/')
                    logging.warning("开始从容器%s中备份到宿主机" % container_id)
                    os.popen(copy_sql)
                    time.sleep(time_buffer)
            else:
                logging.error("数据库 %s 不存在，请检查后重新运行！" % db_schema)
        except Exception as e:
            logging.error("执行备份单/多模式的方法报错\n%s" % traceback.format_exc())
        finally:
            con_pg.close()
            logging.info("关闭数据库连接")
            self.emails()

    @execute_rmdir
    @execute_time
    def tables(self):
        """备份单/多表的方法"""
        logging.info("进入执行备份单/多表的方法")
        con_pg = None
        try:
            logging.info("正在连接数据库……")
            con_pg = self.conn_pgsql()
            curs = con_pg.cursor()
            curs.execute(self.sql)
            results = curs.fetchall()
            databases = []
            for result in results:
                result = list(result)
                databases.append(result[0])
            if db_table in databases:
                logging.info("开始备份 %s 表" % tables)
                for table in tables:
                    dumps = "docker exec -i -d {0} /bin/bash -c 'pg_dump -U postgres {1} -t {2}.{3} > /{4}.sql'".format(
                        container_id, db_table, table_schemas, table, table)
                    os.popen(dumps)
                    time.sleep(time_buffer)
                    copy_sql = "docker cp {0}:/{1}.sql {2}".format(
                        container_id, table, Backup_path + self.Dirbackup + '/')
                    logging.warning("开始从容器%s中备份到宿主机" % container_id)
                    os.popen(copy_sql)
                    time.sleep(time_buffer)
            else:
                logging.error("数据库 %s 不存在，请检查后重新运行！" % db_table)
        except Exception as e:
            logging.error("执行备份单/多表的方法报错\n%s" % traceback.format_exc())
        finally:
            con_pg.close()
            logging.info("关闭数据库连接")
            self.emails()

    @execute_rmdir
    @execute_time
    def emails(self):
        """发送邮件的方法"""
        logging.info("进入执行发送邮件的方法")
        try:
            mailserver = email_information['mailserver']
            username_send = email_information['username_send']
            password = email_information['password']
            for user in username_to:
                username_recv = user
                mail = MIMEText(email_text['mail_body'])
                mail['Subject'] = email_text['mail_head']
                mail['From'] = username_send
                mail['To'] = username_recv

                smtp = smtplib.SMTP(mailserver, port=email_information['port'])
                smtp.login(username_send, password)
                smtp.sendmail(username_send, username_recv, mail.as_string())
                smtp.quit()
        except Exception as e:
            logging.error("执行发送邮件的方法报错%s" % traceback.format_exc())
        else:
            logging.info("执行发送邮件的方法成功，请到邮箱查收！")

    @execute_time
    def con_task(self, func):
        """执行定时任务的方法"""
        logging.info("进入执行定时任务的方法")
        try:
            blocking = BlockingScheduler()  # 实例化父类
            blocking.add_job(func, 'cron', day_of_week=cron_time['week'], hour=cron_time['hour'],
                             minute=cron_time['minute'])
            blocking.start()
        except (Exception, SystemExit, KeyboardInterrupt) as e:
            logging.error("定时任务执行发生错误%s" % traceback.format_exc())

    def rmdir(self, day):
        """执行删除指定日期之前备份的方法"""


if __name__ == '__main__':
    """主程序"""
    databasebr = DatabaseBR()
    if way == '1':
        '''单/多模式备份'''
        logging.info("===选择了'单/多模式备份',等待定时器执行===")
        databasebr.con_task(databasebr.schemas)
    elif way == '2':
        '''单库'''
        logging.info("===选择了'单库备份',等待定时器执行===")
        databasebr.con_task(databasebr.backup_onedb)
    elif way == '3':
        '''单/多表备份'''
        logging.info("===选择了'单/多表备份',等待定时器执行===")
        databasebr.con_task(databasebr.tables)
    elif way == '4':
        '''整库备份'''
        logging.info("===选择了'整库备份',等待定时器执行===")
        databasebr.con_task(databasebr.backing)
    elif way == '5':
        '''多库备份'''
        logging.info("===选择了'多库备份',等待定时器执行===")
        databasebr.con_task(databasebr.backup_doubledb)
    else:
        logging.error("config配置中的'way'选择的备份模式错误！已结束")
