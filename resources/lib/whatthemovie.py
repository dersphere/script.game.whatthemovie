import mechanize
import time
import datetime
import re
from urllib import urlencode
from BeautifulSoup import BeautifulSoup


class WhatTheMovie:

    MAIN_URL = 'http://whatthemovie.com'

    def __init__(self, user_agent):
        # Get browser stuff
        self.cookies = mechanize.LWPCookieJar()
        self.browser = mechanize.Browser()
        self.browser.set_cookiejar(self.cookies)
        self.browser.addheaders = [('user-agent', user_agent)]
        # Set empty returns
        self.shot = dict()
        self.last_shots = list()

    def login(self, user, password, cookie_path):
        logged_in = False
        try:
            self.cookies.revert(cookie_path)
            cookie_found = True
        except IOError:
            cookie_found = False
        if cookie_found:
            logged_in_user = self._getUsername(retrieve=True)
            if logged_in_user == user:
                logged_in = 'cookie'
        if not logged_in:
            login_url = '%s/user/login' % self.MAIN_URL
            data_dict = dict()
            data_dict['name'] = user
            data_dict['upassword'] = password
            data = urlencode(data_dict)
            req = mechanize.Request(login_url, data)
            self.browser.open(req)
            logged_in_user = self._getUsername()
            if logged_in_user:
                logged_in = 'auth'
                self.cookies.save(cookie_path)
        return logged_in

    def _getUsername(self, retrieve=False):
        # only retrieve if there is no previous retrieve which we can use
        if retrieve:
            self.browser.open(self.MAIN_URL)
        html = self.browser.response().read()
        tree = BeautifulSoup(html)
        section = tree.find('li', attrs={'class': 'secondary_nav',
                                         'style': 'margin-left: 0'})
        if section:
            username = section.a.span.string
        else:
            username = None
        return username

    def setRandomOptions(self, settings):
        option_url = '%s/shot/setrandomoptions' % self.MAIN_URL
        self._sendAjaxReq(option_url, settings)

    def _sendAjaxReq(self, url, data_dict=None):
        if data_dict:
            post_data = urlencode(data_dict)
        else:
            post_data = ' '
        req = mechanize.Request(url, post_data)
        req.add_header('Accept', 'text/javascript, */*')
        req.add_header('Content-Type',
                       'application/x-www-form-urlencoded; charset=UTF-8')
        req.add_header('X-Requested-With', 'XMLHttpRequest')
        self.browser.open(req)
        response = self.browser.response().read()
        response_c = response.replace('&amp;', '&').decode('unicode-escape')
        return response_c

    def getShot(self, shot_id):
        if shot_id == 'last':
            if self.last_shots:
                self.shot = self.last_shots.pop()
        else:
            if self.shot:  # if there is already a shot - put it in list
                self.last_shots.append(self.shot)
            if (shot_id.isdigit() or
                shot_id == 'random' or
                shot_id in self.shot['nav'].keys()):
                self.shot = self.scrapeShot(shot_id)
        return self.shot

    def scrapeShot(self, shot_id):
        self.shot = dict()
        shot_url = '%s/shot/%s' % (self.MAIN_URL, shot_id)
        self.browser.open(shot_url)
        html = self.browser.response().read()
        tree = BeautifulSoup(html)
        # id
        shot_id = tree.find('li', attrs={'class': 'number'}).string.strip()
        # prev/next
        nav = dict()
        section = tree.find('ul', attrs={'id': 'nav_shots'}).findAll('li')
        nav_types = ((0, 'first'), (1, 'prev'), (2, 'prev_unsolved'),
                     (4, 'next_unsolved'), (5, 'next'), (6, 'last'))
        for i, nav_type in nav_types:
            if section[i].a:
                nav[nav_type] = section[i].a['href'][6:]
            else:
                nav[nav_type] = None
        # image url
        image_url = tree.find('img', alt='guess this movie snapshot')['src']
        # languages
        lang_list = dict()
        lang_list['main'] = list()
        lang_list['hidden'] = list()
        section = tree.find('ul', attrs={'class': 'language_flags'})
        langs_main = section.findAll(lambda tag: len(tag.attrs) == 0)
        for lang in langs_main:
            if lang.img:
                lang_list['main'].append(lang.img['src'][-6:-4])
        langs_hidden = section.findAll('li',
                                       attrs={'class': 'hidden_languages'})
        for lang in langs_hidden:
            if lang.img:
                lang_list['hidden'].append(lang.img['src'][-6:-4])
        lang_list['all'] = lang_list['main'] + lang_list['hidden']
        # date
        date = None
        date_info = tree.find('ul',
                              attrs={'class': 'nav_date'}).findAll('li')
        if len(date_info) >= 4:
            date_s = time.strptime('%s %s %s' % (date_info[1].a.string,
                                                 date_info[2].a.string,
                                                 date_info[3].a.string[:-2]),
                                   '%Y %B %d')
            date = datetime.datetime.fromtimestamp(time.mktime(date_s))
        # posted by
        sections = tree.find('ul',
                             attrs={'class': 'nav_shotinfo'}).findAll('li')
        if sections[0].a:
            posted_by = sections[0].a.string
        else:
            posted_by = None
        # solved
        solved = dict()
        try:
            solved_string, solved_count = sections[1].string[8:].split()
            if solved_string == 'solved':
                solved['status'] = True
                solved['count'] = int(solved_count.strip('()'))
        except:
            solved['status'] = False
            solved['count'] = 0
        try:
            solved['first_by'] = sections[2].a.string
        except:
            solved['first_by'] = None
        # already solved
        already_solved = False
        js_list = tree.findAll('script',
                               attrs={'type': 'text/javascript'},
                               text=re.compile('guess_problem'))
        if js_list:
            already_solved = True
        # voting
        voting = dict()
        section = tree.find('script',
                            attrs={'type': 'text/javascript'},
                            text=re.compile('tt_shot_rating_stars'))
        r = ('<strong>(?P<overall_rating>[0-9.]+|hidden)</strong> '
             '\((?P<votes>[0-9]+) votes\)'
             '(<br>Your rating: <strong>(?P<own_rating>[0-9.]+)</strong>)?')
        if section:
            voting = re.search(r, section).groupdict()
        # tags
        tags = list()
        tags_list = tree.find('ul', attrs={'id':
                                           'shot_tag_list'}).findAll('li')
        for tag in tags_list:
            if tag.a:
                tags.append(tag.a.string)
        # shot_type
        section = tree.find('h2', attrs={'class':
                                         'topbar_title'}).string.strip()
        shot_type = 0  # Unknown
        if section == 'New Submissions':
            shot_type = 1
        elif section == 'Feature Films':
            shot_type = 2
        elif section == 'The Archive':
            shot_type = 3
        elif section == 'Rejected Snapshots':
            shot_type = 4
        # gives_point
        gives_point = False
        if shot_type == 2 and not already_solved:
            gives_point = True
        # bookmarked
        if tree.find('li', attrs={'id': 'watchbutton'}):
            bookmark_link = tree.find('li', attrs={'id': 'watchbutton'}).a
            try:
                if bookmark_link['class'] == 'active':
                    bookmarked = True
            except KeyError:
                bookmarked = False
        else:
            bookmarked = None  # Not logged in
        # favourite
        if tree.find('li', attrs={'class': 'love'}):
            favourite_link = tree.find('li', attrs={'class': 'love'}).a
            try:
                if favourite_link['class'] == 'active':
                    favourite = True
            except KeyError:
                favourite = False
        else:
            favourite = None  # Not logged in
        # Snapshot of the Day
        sotd = False
        if tree.find('div', attrs={'class': 'sotd_banner'}):
            sotd = True
        # Solvable
        solvable = False
        section = tree.find('li', attrs={'id': 'solutionbutton'})
        if section is not None:
            try:
                if section.a['class'] == 'inactive':
                    solvable = False
            except KeyError:
                solvable = True
        # create return dict
        self.shot['shot_id'] = shot_id
        self.shot['image_url'] = image_url
        self.shot['lang_list'] = lang_list
        self.shot['posted_by'] = posted_by
        self.shot['solved'] = solved
        self.shot['date'] = date
        self.shot['already_solved'] = already_solved
        self.shot['voting'] = voting
        self.shot['tags'] = tags
        self.shot['shot_type'] = shot_type
        self.shot['gives_point'] = gives_point
        self.shot['nav'] = nav
        self.shot['bookmarked'] = bookmarked
        self.shot['favourite'] = favourite
        self.shot['sotd'] = sotd
        self.shot['solvable'] = solvable
        print self.shot
        return self.shot

    def downloadFile(self, url, local_path):
        self.browser.retrieve(url, local_path, )

    def guessShot(self, title_guess, shot_id):
        answer = dict()
        answer['is_right'] = False
        post_url = '%s/shot/%s/guess' % (self.MAIN_URL, shot_id)
        post_dict = {'guess': title_guess.encode('utf8')}
        response_c = self._sendAjaxReq(post_url, post_dict)
        # ['right'|'wrong']
        if response_c[6:11] == 'right':
            answer['is_right'] = True
            answer['title_year'] = response_c.split('"')[3]
            if self.shot['shot_id'] == shot_id:
                self.shot['already_solved'] = True
        return answer

    def rateShot(self, shot_id, user_rate, rerated='false'):
        url = '%s/shot/%s/rate.js' % (self.MAIN_URL, shot_id)
        user_rate_5 = float(user_rate) / 2
        rating_dict = dict()
        rating_dict['identity'] = 'shot_rating_stars_%s' % shot_id
        rating_dict['rated'] = user_rate_5
        rating_dict['rerated'] = rerated
        self._sendAjaxReq(url, rating_dict)
        if self.shot['shot_id'] == shot_id:
            self.shot['voting']['own_rating'] = str(user_rate)

    def bookmarkShot(self, shot_id, new_state):
        if new_state == True:
            url = '%s/shot/%s/watch' % (self.MAIN_URL, shot_id)
        else:
            url = '%s/shot/%s/unwatch' % (self.MAIN_URL, shot_id)
        self._sendAjaxReq(url)
        if self.shot['shot_id'] == shot_id:
            self.shot['bookmarked'] = new_state

    def favouriteShot(self, shot_id, new_state):
        if new_state == True:
            url = '%s/shot/%s/fav' % (self.MAIN_URL, shot_id)
        else:
            url = '%s/shot/%s/unfav' % (self.MAIN_URL, shot_id)
        self._sendAjaxReq(url)
        if self.shot['shot_id'] == shot_id:
            self.shot['favourite'] = new_state

    def solveShot(self, shot_id):
        url = '%s/shot/%s/showsolution' % (self.MAIN_URL, shot_id)
        ajax_answer = self._sendAjaxReq(url)
        r = '<strong>(?P<solution>.+)\.\.\.</strong>'
        solved_title = re.search(r, ajax_answer).group('solution')
        if self.shot['shot_id'] == shot_id:
            self.shot['already_solved'] = True
        return solved_title

    def getScore(self, username):
        score = 0
        profile_url = '%s/user/%s/' % (self.MAIN_URL, username)
        self.browser.open(profile_url)
        html = self.browser.response().read()
        tree = BeautifulSoup(html)
        box = tree.find('div', attrs={'class': 'box_white'})
        score = box.p.strong.string[0:-13]
        return score
