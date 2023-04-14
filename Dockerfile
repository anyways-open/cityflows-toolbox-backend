FROM debian:11.5
RUN apt-get update -y && apt-get install -y nano python3-pip python3-dev build-essential default-libmysqlclient-dev libspatialindex-dev apache2 apache2-dev libapache2-mod-wsgi-py3 logrotate git
RUN python3 -m pip  install python-dateutil
RUN python3 -m pip  install django
RUN python3 -m pip  install django-cors-headers
RUN python3 -m pip install psycopg2-binary
RUN python3 -m pip install pandas
RUN python3 -m pip install statsmodels
RUN python3 -m pip install scikit-learn
RUN python3 -m pip install holidays
RUN python3 -m pip install django-oauth-toolkit
RUN pip3 install django-bootstrap3 
COPY ./apache.conf /etc/apache2/sites-available
COPY mount_point/ /app/
RUN a2dissite 000-default
RUN a2ensite apache

CMD apachectl -D FOREGROUND