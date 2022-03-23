
import requests    
import random
import time
import os
import json
from bs4 import BeautifulSoup

from const import *
from configs import *
from utils import *


proxy_manager = ProxyManager("./proxy_list.txt", 30)


def request_html(url, params={}):
    time.sleep(random.randint(5,8))

    kwargs = {
        'url': url,
        'params': params,
        'headers': {'User-Agent': USER_AGENT,'Cookie': COOKIE}
    }

    req = getattr(requests, 'get')(**kwargs)
    print(f'getting: {req.url}, status: {req.status_code}')

    if req.status_code != 200:
        print(f'req fails: {req.url}')
        # 试一下别的proxy （并不稳定）
        if proxy_manager is not None:
            proxy = proxy_manager.get_proxy()
            print(f'------proxy: {proxy}')
            kwargs["proxies"] = {
                "http": "http://%s" % proxy
                ,"https": "https://%s" % proxy
            }
        retry_req = getattr(requests, 'get')(**kwargs)
        print(f'[Using proxy]getting: {req.url}, status: {req.status_code}')
        if retry_req.status_code != 200:
            return None
        return retry_req.text

    return req.text


def crawl_group(group_id):
    print(f'start crawling group: {group_id}')

    # TODO: 页数从第一次请求的结果进行解析
    pages = 35
    discuss_selected = {}
    url = GROUP_TOPICS_BASE_URL.format(DOUBAN_BASE_HOST, group_id)
    
    for p in range(pages):
        try: 
            page_html = request_html(url, {'start': p * 25})
            if page_html is not None:
                print(f'request success for page {p}')
                # 写入文件查看 html 内容
                # with open("./discuss_list_html.txt", "w") as text_file:
                #     print(f"{page_html}", file=text_file)

                soup = BeautifulSoup(page_html,'lxml')
                for row in soup.select('table[class="olt"] tr[class=""]'):
                    is_not_elite_topic = row.select_one('td[class="title"] span[class="elite_topic_lable"]') is None
                    reply_cnt = row.select_one('td[class="r-count"]').string
                    if is_not_elite_topic and (not reply_cnt or int(reply_cnt) < REPLY_COUNT_LOWER_LIMIT):
                        continue

                    title_line = row.select_one('td[class="title"] a')
                    title = title_line["title"]
                    discuss_url = title_line["href"]

                    if discuss_url not in discuss_selected:
                        discuss_selected[discuss_url] = {
                            'title': title,
                            'url': discuss_url,
                        }
        except Exception as e:
            print(f'error for crawling page {p}: {str(e)}')
            continue
        
    with open('discuss_selected.json', 'w') as f:
        json.dump(discuss_selected, f)
    
    if not os.path.exists(DISCUSSION_OUTPUT_PATH):
        os.makedirs(DISCUSSION_OUTPUT_PATH)

    for key_url in discuss_selected:
        try: 
            crawl_discuss(key_url)
        except Exception as e:
            print(f'error for crawling discuss {key_url}: {str(e)}')
            continue


def crawl_discuss(url):
    discuss_html = request_html(url)
    if discuss_html is None:
        return 

    print(f'request discuss success: {url}')
    # # 写入文件查看 html 内容
    # with open("./discuss_detail_html_no_pager.txt", "w") as text_file:
    #     print(f"{discuss_html}", file=text_file)

    soup = BeautifulSoup(discuss_html,'lxml')
    # 分页
    pages = 1
    paginator = soup.select_one('div[class="paginator"]')
    if paginator is not None:
        pages = int(paginator.select_one('span[class="thispage"]')['data-total-page'])

    # 主贴
    main_title = soup.find('title').string
    main_content = str(soup.find("div", class_=["rich-content", "topic-richtext"]).contents)
    author = soup.select_one('h3 span[class="from"] a').string
    create_time = soup.find("span", class_=["create-time", "color-green"]).string

    # 回复
    reply_list = crawl_discuss_reply(soup, url, pages)

    # summary
    content = {
        KEY_URL: url
        ,KEY_MAIN_TITLE: str(main_title).strip().replace('/', '|')
        ,KEY_MAIN_CONTENT: str(main_content).strip()
        ,KEY_AUTHOR: str(author).strip()
        ,KEY_CREATE_TIME: create_time
        ,KEY_REPLY_LIST: reply_list
    }
    write_markdown(content)


def crawl_discuss_reply(soup, url, pages=1):
    result = parse_discuss_reply(soup)
    if pages == 1:
        return result

    for page in range(1, pages):
        discuss_html = request_html(url, {'start': page * 100})
        if discuss_html is None:
            continue
        page_soup = BeautifulSoup(discuss_html,'lxml')
        result.extend(parse_discuss_reply(page_soup))
    return result
    

def parse_discuss_reply(soup):
    reply_list = []
    for row in soup.find_all('li', class_=['clearfix', 'comment-item', 'reply-item']):
        reply_author = row.select_one('div[class="bg-img-green"] h4 a').string
        reply_content = row.select_one('p[class="reply-content"]').string 
        reply_pic = ''
        pic_path = row.select_one('div[class="comment-photos"] div[class="cmt-img-wrapper"] div[class="cmt-img"] img')
        if pic_path:
            reply_pic = pic_path["data-photo-url"]

        reply_list.append({
            KEY_REPLY_AUTHOR: str(reply_author).strip()
            ,KEY_REPLY_CONTENT: str(reply_content).strip()
            ,KEY_REPLY_PIC: reply_pic
        })
    return reply_list


def write_markdown(content):
    file_name_md = content[KEY_MAIN_TITLE] + '.md'

    with open(DISCUSSION_OUTPUT_PATH + '/' + file_name_md, 'w', encoding='utf-8') as dis_file:
        title_line = '# {0}\n'.format(content[KEY_MAIN_TITLE])
        title_subline = '{0}, {1}\n'.format(content[KEY_AUTHOR], content[KEY_CREATE_TIME])
        main_content = '#### {0}\n'.format(content[KEY_MAIN_CONTENT])
        main_separate_line = '======================================\n\n'

        main_content = title_line + title_subline + main_content + main_separate_line
        dis_file.write(main_content)

        for reply in content[KEY_REPLY_LIST]:
            content_line = '###### [{0}]: {1}\n'.format(reply[KEY_REPLY_AUTHOR], reply[KEY_REPLY_CONTENT])
            content_pic = reply[KEY_REPLY_PIC]
            content_pic_line = '' if len(content_pic) == 0 else 'pic: ({0})\n'.format(content_pic)
            separate_line = '---------------------------------------\n\n'

            reply_content = content_line + content_pic_line + separate_line
            dis_file.write(reply_content)
  

if __name__ == '__main__':
    crawl_group(GROUP_ID)

    # Test
    # crawl_discuss('https://www.douban.com/group/topic/262046344/')
    # crawl_discuss('https://www.douban.com/group/topic/262029457/')

