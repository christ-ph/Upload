FROM python:3.11-slim

WORKDIR /app

COPY server.py auth.py database.py config.py ./
COPY index.html login.html dashboard.html ./

RUN mkdir -p public_uploads private_uploads

EXPOSE 8080

CMD ["python", "server.py"]