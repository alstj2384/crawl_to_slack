import requests
import time
from bs4 import BeautifulSoup
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging
import json

# 디버거 세팅
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fd = logging.FileHandler('file.log')
fd.setLevel(logging.ERROR)
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fd.setFormatter(f_format)
logger.addHandler(fd)


# config file open
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# config.json
slack_token = config['slack_token']
base_url = config['base_url']
notices = config["notices"]

class WebCrawler:

    def __init__(self, slack_token, base_url):
        self.client = WebClient(token=slack_token)
        self.base_url = base_url

    # 웹 크롤링
    def fetch_data(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status() # 응답 코드가 200이 아닌 경우 에러
        except requests.exceptions.RequestException as e: # 모든 경우의 Exception
            logger.error(f"Error: {str(e)}")
            return None

        return BeautifulSoup(response.text, 'html.parser')

    def parse_data(self, soup):
        """
        :개선 해야될 사항: 학교 학사공지, 장학 공지의 html 태그 형식과 컴퓨터 공학과
        html 태그 형식이 달라 구분해야함. (우선은 학사공지, 장학공지를 추출할 수 있도록 함)
        생각중인 방법 : config파일에 사이트별로 select 경로를 재작성하여 다른 페이지를 금방 추출 할 수 있도록 수정
        아직은 유연하지 못함.. (함수의 기능이 독립적이지 않음)\n
        :param soup: parsed text file
        :return: tuple of title and link
        """
        table = soup.select_one('div.type-table')
        for span in table.find_all('span', class_='mark'):
            span.decompose()
        links = table.find_all('a')
        titles = table.select('tbody > tr > td.subject > a')

        return list(zip(titles,links))

    def read_previous_notices(self, filepath):
        """
        이전 데이터 불러오기
        :return: 기존에 저장되어 있던 text
        """
        with open(filepath, "a+", encoding='UTF-8') as fd:
            fd.seek(0)
            return fd.read()

    def write_notices_to_file(self, filepath, title, link):
        """
        :param filepath: 작성될 파일의 경로
        :param title: 파일에 쓰여질 제목
        :param link: 파일에 쓰여질 링크
        """
        with open(filepath, "a", encoding='UTF-8') as fd:
            fd.write(f"{title}\n{link}\n")

    def connect_Web(self, crawl, order):
        """
        사이트 접속 및 파싱
        :param crawl: WebCrawler 객체
        :param order: json 파일 내 공지사항 접근 변수(0,1,2...)
        :return: parsed data
        """
        soup = crawl.fetch_data(notices[order]['url'])
        return crawl.parse_data(soup)


    def update_notice(self, data, order):
        """
        data 튜플(title, link)과 기존에 작성된 파일을 비교하여 없는 제목을 발견할 경우
        파일에 새로운 내용 추가 & slack 메시지 post
        # notice[0] = 장학 공지
        # notice[1] = 학교 학사 공지
        # notice[2] = 과 학사 공지
        :param data: data tuple(title, link)
        :param order(int): 0,1,2... config.json에 작성된 공지사항의 순서
        """
        selected_path = notices[order]['path']
        selected_channel = notices[order]['channel']


        script = self.read_previous_notices(selected_path)
        for title, link in data:
            if script.find(title.get_text().strip()) == -1:
                in_url = base_url + link.get('href')
                self.write_notices_to_file(selected_path, title.get_text().strip(), in_url)
                self.post_to_slack(selected_channel, title.get_text().strip(), in_url)


    def post_to_slack(self, channelId, title, in_url):
        """
        개선 해야될 사항 : 보내는 메시지의 폼을 좀 바꿔야할듯! 너무 단조롭다.
        :param channelId: 슬랙 채널 ID(C0######..)
        :param title: 메시지로 보낼 내용
        :param in_url: 메시지로 보낼 주소(링크)
        """
        try:
            response = self.client.chat_postMessage(
                channel=channelId,
                blocks=[
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": title
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": in_url
                            }
                        ]
                    }
                ]
            )
        except SlackApiError as e:
            logger.error(e.response['error'])


def run():
    crawl = WebCrawler(slack_token, base_url)
    for i in range(2):
        data = crawl.connect_Web(crawl, i)
        crawl.update_notice(data, i)
        print("실행 완료 다음으로..")
        time.sleep(2)