import boto3
import base64
from botocore.exceptions import ClientError

import json
import re                       # 정규식 표현을 위한 모듈
import requests                 # URL 요청을 위한 모듈
import pymysql                  # DB 모듈
import logging                  # 로깅 모듈
import time
import mimetypes                # For Guess Mimetime
import multiprocessing
from os import path, environ             # 경로 존재 여부 확인
from bs4 import BeautifulSoup   # Title tag 를 뽑기 위한 모듈
from requests.exceptions import ConnectTimeout, ReadTimeout
import sentry_sdk

def get_secret():

    secret_name = environ.get('secret_name')
    region_name = "ap-northeast-2"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    # In this sample we only handle the specific exceptions for the 'GetSecretValue' API.
    # See https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    # We rethrow the exception by default.

    try:
        print(f"Secret Manager 에서 데이터 가져오는 중....")
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            # An error occurred on the server side.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # You provided an invalid value for a parameter.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            # You provided a parameter value that is not valid for the current state of the resource.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            # We can't find the resource that you asked for.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            decoded_binary_secret = base64.b64decode(
                get_secret_value_response['SecretBinary'])

        secret = json.loads(secret)
        print(f"Secret Manager 에서 데이터 가져오기 성공....")
        return secret

secret = get_secret()
sentry_sdk.init(
    secret['SENTRY_URL'],

    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0
)

db = pymysql.connect(host=secret["host"],
                     port=int(secret["port"]),
                     user=secret["username"],
                     passwd=secret["password"],
                     db=secret["dbname"],
                     charset='utf8mb4',
                     autocommit=True
                     )


headers = {
    'user-agent': 'Mozilla/5.0 (compatible; Tullamarine-C11Bot/3.0; https://c11.kr/bot/bot.html)'}


class DB:
    def __init__(self) -> None:
        self.cursor = db.cursor()

    def testDB(self):
        sql = ""
        self.cursor.execute(sql)
        num = self.cursor.fetchone()
        if num[0] == 1:
            print("데이터베이스 접속 완료...")
        return True

    def get_cursor(self):
        return self.cursor

    def get_url(self, id=None) -> set:
        if id == None:
            sql = ""
            # 12초 - 14초 걸림
            # sql = ""
            self.cursor.execute(sql)
            id, url = self.cursor.fetchone()

        else:
            sql = ""
            self.cursor.execute(sql, id)
            id, url = self.cursor.fetchone()

        return (str(id), url)

    def save(self, id, title):
        sql = ""
        try:
            self.cursor.execute(sql, [title, id])
            return True
        except Exception as e:
            print(f"Title {id} is not saved. ,{e}")
            return False

    def make_error(self, cause_by):  # title_status
        sql = ""
        self.cursor.execute(sql, [cause_by, self.id])


class Tullamarine(DB):
    def __init__(self, id: int):
        self.id = str(id)
        self.filesize = 0
        self.target_url = DB().get_url(self.id)[1]
        self.encoding = None
        self.cursor = DB().get_cursor()
        print("=" * 15)
        print(f"=> 현재 진행중인 ID: {self.id}")
        print(f"=> 현재 진행중인 URL: {self.target_url}")
        self.make_reservation()
        print("=" * 15)

    def download_file(self) -> set:
        Err = False
        filesize = 0  # 파일 사이즈 0 초기화
        target_path = "./downloads"
        startAt = time.time()
        maximum = 31457280  # Maximum 30MB
        try:
            file_header = requests.head(
                self.target_url, stream=True, timeout=5, allow_redirects=True, headers=headers)
            self.encoding = file_header.encoding

        except requests.exceptions.Timeout:
            self.make_error("Timeout, Timeout 오류 발생")
            Err = True
        except requests.exceptions.TooManyRedirects:
            self.make_error("Too Many Redirects 오류 발생")
            Err = True
        except requests.exceptions.RequestException as e:
            self.make_error("기타 오류 발생")
            Err = True

        except Exception as e:
            self.make_error("알 수 없는 오류 발생" + e)
            Err = True

        if Err == True:
            return (0, self.target_url, None)

        try:
            if path.exists(target_path + "/" + self.id + ".html"):
                print(f"Link ID {self.id} ==> Already Exists")
                return (self.id, self.target_url, file_header.encoding)

            if file_header.headers.get('Content-Type'):
                if "text/html" not in file_header.headers["content-type"]:
                    self.make_error("Content Type(MIME) 이 text/html 이 아님")
                    return (0, self.target_url, None)
            if file_header.headers.get('Content-Length'):
                if int(file_header.headers.get('Content-Length')) > maximum:
                    # File reached exceed maximum
                    self.make_error("Content-Length 길이 초과")
                    return (0, self.target_url, file_header.encoding)

            print(f"Link ID {self.id} ==> Download is Started")

            file = requests.get(self.target_url, headers=headers,
                                stream=True, timeout=5, allow_redirects=True)
            handle = open(target_path + '/' + str(self.id) + ".html", "wb")
            # 1MB 단위로 Chunk
            for chunk in file.iter_content(chunk_size=1024 * 1024):
                if chunk:   # chunk시, handle.write 수행
                    handle.write(chunk)
                if time.time() - startAt > 30:  # 최초 다운로드 후 30초 후면, Timeout 처리
                    self.make_error("Timeout, 30초 이상의 긴 다운로드 수행")
                    raise ValueError('timeout reached')
                if filesize > maximum:
                    self.make_error("30MB 초과")
                    raise ValueError("This is not html file")
                handle.flush()
            handle.close()

        except Exception as e:
            print(f"ID: {self.id} 오류 발생 URL: {self.target_url}")
            print("Exception: >> ", e, "Err", e.with_traceback)
            return (0, self.target_url, file_header.encoding)

        return (self.id, self.target_url, self.encoding)

    def get_title(self, encoding="utf-8"):
        try:
            soup = BeautifulSoup(
                open("./downloads/" + self.id + ".html", encoding="utf-8"),
                'html.parser')
        except UnicodeDecodeError:
            self.make_error("유니코드 오류, 웹사이트가 아닐 수 있음")
            return False
            # 예외 URL 추가
            # 카카오 오픈 채팅

        regex_og_title = ["https?:\/\/open.kakao.com\/o\/[a-zA-Z0-9]+",
                          "https?:\/\/open.kakao.com\/me\/[a-zA-Z0-9_-]+",
                          "https?:\/\/(www|).?youtube.com\/channel\/[a-zA-Z-0-9_-]+"]
        for og_title in regex_og_title:
            if re.match(og_title, self.target_url) != None:
                if soup.find("meta",  property="og:title").get_text() is not None:
                    title = soup.find("meta",  property="og:title").get_text()
                    title = title.strip()
                    return title

        if soup.title == None or "":
            print(f"Untitled URL: {self.target_url} ")
            self.make_error("존재하지 않는 제목")
            return ""
        else:
            title = soup.title.get_text().strip()
            re.sub("(?:\r\n|\r|\n)", "", title)
            return title

    def make_reservation(self):
        sql = ""
        self.cursor.execute(sql, self.id)
        print(f"{self.id} Pending 전환 완료")
        return True

    def do(self):
        id, url, encoding = self.download_file()
        print(id, url, encoding)
        if id == 0:
            return True
        else:
            title = self.get_title(encoding)
            print(f"title ==> {title}")
            self.save(id, title)
            print(f"Link ID {self.id} ==> Done.")
            return True


if __name__ == "__main__":
    get_secret()
    d = DB()
    d.testDB()

    while True:
        id, url = d.get_url()
        t = Tullamarine(id).do()

    # For Debug Purpose.
    # t = Tullamarine(id).do() # Normal
    # t = Tullamarine(869791).do() # Debug
    # t = Tullamarine(869831).do()
    # print(mimetypes.guess_all_extensions('./downloads/869818.html'))
    # print(mimetypes.guess_extension(target_path + '/' + self.id + ".html"))
