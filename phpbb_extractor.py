import os
import sys
import requests
import justext
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, parse_qs, urljoin
import configparser


config = configparser.ConfigParser()
config.read('config.properties')
headers = dict(config['Headers'])

domain = "forum_name"
base_url = "https://example-forum-base-url.com"
forum_skip = 25
topic_skip = 10
MIN_TEXT_LEN = 300


def isForum(url):
    return "/viewforum.php" in url


def isTopic(url):
    return "/viewtopic.php" in url and "t=" in url


def find_links(content, query_param, isType):
    urls = set()
    soup = BeautifulSoup(content, 'lxml')
    for link in soup.find_all('a'):
        if link.has_attr('href') and isType(link['href']):
            link_href = link['href']
            # sometimes ';' is placed in url instead of '&'
            link_href.replace(";", "&")
            parsed_url = urlparse(link_href)

            query_current = parse_qs(parsed_url.query)
            if (parsed_url.path.startswith(".")):
                parsed_url = urlparse(urljoin(base_url, parsed_url.path))
            params = {query_param: query_current[query_param]}
            if "start" in query_current.keys():
                params["start"] = query_current["start"]

            simplified_url = urlunparse(
                [parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", urlencode(params, doseq=1), ""])
            urls.add(simplified_url)
    return urls


# download forums urls
def extract_forums(url, session=requests.Session()):
    forums = set()

    response = session.get(url, headers=headers)
    if response.status_code == 200:
        forums = find_links(response.content, query_param='f', isType=isForum)
    return forums


def construct_forum_url(forum, page_start=0):
    return base_url + "viewforum.php?" + urlencode({"f": forum, "start": page_start})


def construct_topic_url(topic, page_start=0):
    return base_url + "viewtopic.php?" + urlencode({"t": topic, "start": page_start})


def fill_forum_pages(forum_pages: dict, skip: int):
    filled_pages = dict()
    for f, start in forum_pages.items():
        for i in range(0, start+skip, skip):
            if f in filled_pages:
                filled_pages[f].append(i)
            else:
                filled_pages[f] = [i]
    return filled_pages


def extract_topics(forum_url, query_param='t'):
    session = requests.Session()
    session.headers.update(headers)
    response = session.get(forum_url, headers=headers)
    topics_urls = set()
    if response.status_code == 200:
        topics_urls = find_links(
            response.content, query_param=query_param, isType=isTopic)
    return topics_urls


def prepare_urls_to_visit():
    all_urls = set()
    session = requests.Session()
    session.headers.update(headers)
    forums_urls = set()
    forums_to_visit = dict()
    for forum_url in extract_forums(base_url, session):
        forums_urls.update(extract_forums(forum_url, session))
    for forum_url in forums_urls:
        cur_forum = parse_forum_topic_page(forum_url)
        if cur_forum["f"] not in forums_to_visit or forums_to_visit[cur_forum["f"]] < cur_forum["start"]:
            forums_to_visit[cur_forum["f"]] = cur_forum["start"]
    # forums_to_visit = extract_pages_to_visit(forums_to_visit, "f")

    forums_pages = dict(
        sorted(fill_forum_pages(forums_to_visit, forum_skip).items()))

    all_urls = set()
    for forum_pages in forums_pages.items():
        forum_id = forum_pages[0]
        for cur_forum_page in forum_pages[1]:
            all_urls.update(extract_topics(
                construct_forum_url(forum_id, cur_forum_page)))

    with open(os.path.join(sys.path[0], domain + "_urls.txt"), 'a', encoding="utf-8") as f:
        f.write("\n".join(all_urls) + "\n")


def extract_text(posts: set):
    content_list = list()
    for post in posts:
        content_list.append(post.getText())
    try:
        jtxt = justext.justext(
            '\n'.join(content_list), justext.get_stoplist("Polish"))
    except Exception as e:
        print("extract_text err: ", e)
        pass
    txt = ""
    for paragraph in jtxt:
        if not paragraph.is_boilerplate:
            txt += paragraph.text + " "
    return txt


def save_to_file(txt: str, number: int):
    if txt is not None and len(txt) >= MIN_TEXT_LEN:
        try:
            with open(domain + "/" + str(number)+".txt", 'w', encoding="utf-8") as f:
                f.write(txt)
        except Exception as e:
            print(e)
    else:
        print("to short: " + str(number) + " " + str(len(txt)))


def download_content(url: str):
    session = requests.Session()
    session.headers.update(headers)
    response = session.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'lxml')

    posts = soup.select('div[class="content"]')
    return extract_text(posts)


def parse_forum_topic_page(url):
    flaten_query_params = dict()
    # sometimes ';' is placed in url instead of '&'
    url.replace(";", "&")
    parsed_url = urlparse(url)

    query_current = parse_qs(parsed_url.query)
    if "start" not in query_current:
        query_current["start"] = ['0']
    for query_param in query_current.items():
        flaten_query_params[query_param[0]] = int(query_param[1][0])
    return flaten_query_params


def download_text(topic_page):
    text = ""
    try:
        for cur_page in range(0, topic_page[1]+topic_skip, topic_skip):
            url = construct_topic_url(topic_page[0], cur_page)
            text += download_content(url)
        save_to_file(text, topic_page[0])
    except Exception as e:
        print(e)
        pass


def extract_pages_to_visit(urls_to_visit_from_file, param_type="t"):
    topics_to_visit = dict()
    for url in urls_to_visit_from_file:
        forum_topic_page = parse_forum_topic_page(url)

        cur_topic = int(forum_topic_page[param_type])
        if "start" in forum_topic_page:
            cur_page = int(forum_topic_page["start"])
        else:
            cur_page = 0
        if cur_topic not in topics_to_visit or topics_to_visit[cur_topic] < cur_page:
            topics_to_visit[cur_topic] = cur_page
    return topics_to_visit


if __name__ == '__main__':
    if not os.path.exists(os.path.join(sys.path[0], domain + "_urls.txt")):
        prepare_urls_to_visit()
    urls_to_visit_from_file = list(line.strip()
                                   for line in open(os.path.join(sys.path[0], domain + "_urls.txt")))

    urls_visited = set(line.strip()
                       for line in open(os.path.join(sys.path[0], domain + "_urls_visited.txt"), "w+"))

    topics_to_visit = extract_pages_to_visit(urls_to_visit_from_file)
    try:
        os.mkdir(domain)
    except FileExistsError:
        pass
    for topic_page in topics_to_visit.items():
        post_number = topic_page[0]
        if (str(post_number) in urls_visited):
            continue
        if (not os.path.exists(domain + "/" + str(post_number)+".txt")):
            download_text(topic_page), topic_page[0]
            with open(domain + "_forum_urls_visited.txt", 'a') as file:
                file.write(str(post_number) + "\n")
