FROM registry.cn-zhangjiakou.aliyuncs.com/dvadmin-pro/python38-base-backend:latest
WORKDIR /parrotAdmin
COPY ./parrotAdmin/ .
RUN awk 'BEGIN { cmd="cp -i ./conf/env.example.py   ./conf/env.py "; print "n" |cmd; }'
RUN python3 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ -r requirements.txt
CMD ["celery", "-A", "application", "worker", "-B", "--loglevel=info"]

