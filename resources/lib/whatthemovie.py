# WhatTheMovie Python Class
# Copyright (C) Tristan 'sphere' Fischer 2011.

from mechanize import Browser, LWPCookieJar
from BeautifulSoup import BeautifulSoup


class WhatTheMovie:

    MAIN_URL = 'http://whatthemovie.com'

    def __init__(self, cookie_path=None):
        # Get browser stuff
        self.cookies = LWPCookieJar()
        self.browser = Browser()
        self.browser.set_cookiejar(self.cookies)
        # Set variables
        self.cookie_path = cookie_path
        # Set empty returns
        self.is_login = False
        self.shot = dict()
        self.username = None
        self.score = None
        self.answer = None

    def _checkLogin(self, url=None):
        self.is_login = False
        if url is not None:
            self.browser.open(url)
        try:
            html = self.browser.response().read()
        except:
            self.browser.open(self.MAIN_URL)
            html = self.browser.response().read()
        tree = BeautifulSoup(html)
        if tree.find('a', href='http://whatthemovie.com/user/logout'):
            self.is_login = True
        return self.is_login

    def login(self, user, password):
        login_url = '%s/user/login/' % self.MAIN_URL
        try:
            self.cookies.revert('cookie.txt')
            #print 'cookie found.'
        except:
            #print 'no cookie found.'
            pass
        if self._checkLogin(login_url):
            #print 'logged in via cookie.'
            self.username = user
        else:
            #print 'need to login.'
            self.browser.select_form(nr=0)
            self.browser['name'] = user
            self.browser['upassword'] = password
            self.browser.submit()
            if self._checkLogin(login_url):
                #print 'logged in via auth.'
                self.cookies.save('cookie.txt')
                self.username = user
            else:
                #print 'could not log in.'
                pass
        return self.is_login

    def getRandomShot(self):
        self.getShot('random')

    def getShot(self, shot_id):
        self.shot = dict()
        random_url = '%s/shot/%s' % (self.MAIN_URL, shot_id)
        self.browser.open(random_url)
        html = self.browser.response().read()
        tree = BeautifulSoup(html)
        shot_id = tree.find('li', attrs={'class': 'number'}).string.strip()
        image_url = tree.find('img', alt='guess this movie snapshot')['src']
        lang_list = list()
        section = tree.find('ul', attrs={'class': 'language_flags'})
        langs = section.findAll(lambda tag: len(tag.attrs) == 0)
        for lang in langs:
            lang_list.append(str(lang.img['alt'])[:-6])
        sections = tree.find('ul',
                             attrs={'class': 'nav_shotinfo'}).findAll('li')
        posted_by = sections[0].a.string
        solved = dict()
        solved['status'] = sections[1].string[8:]
        try:
            solved['first_by'] = sections[2].a.string
        except:
            solved['first_by'] = 'nobody'
        self.shot['shot_id'] = shot_id
        self.shot['image_url'] = image_url
        self.shot['lang_list'] = lang_list
        self.shot['posted_by'] = posted_by
        self.shot['solved'] = solved
        # fixme, only for debug
        print 'debug languages: %s' % str(self.shot['lang_list'])
        return self.shot

    def guessShot(self, title_guess, shot_id=None):
        self.answer_is_right = False
        if not shot_id:
            shot_id = self.shot['shot_id']
        post_url = '%s/shot/%s/guess' % (self.MAIN_URL, shot_id)
        self.browser.open(post_url, 'guess=%s' % title_guess)
        answer = str(self.browser.response().read())[6:11]
        # ['right'|'wrong']
        if answer == 'right':
            self.answer_is_right = True
        return self.answer_is_right

    def getScore(self, username=None):
        self.score = 0
        if not username:
            #print 'No username given trying logged in user.'
            if not self.username:
                #print 'Not logged in.'
                return self.score
            else:
                username = self.username
        profile_url = '%s/user/%s/' % (self.MAIN_URL, username)
        self.browser.open(profile_url)
        html = self.browser.response().read()
        tree = BeautifulSoup(html)
        box = tree.find('div', attrs={'class': 'box_white'})
        self.score = box.p.strong.string[0:-13]
        return self.score