#!/usr/bin/env python3

import requests
import json
import time
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
import re

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    G = Fore.GREEN
    R = Fore.RED
    Y = Fore.YELLOW
    C = Fore.CYAN
    M = Fore.MAGENTA
    W = Fore.WHITE
    X = Style.RESET_ALL
except ImportError:
    G = R = Y = C = M = W = X = ''

class Email2Profile:
    def __init__(self, email, timeout=15, threads=5, output=None):
        self.email = email.lower()
        self.username = email.split('@')[0]
        self.domain = email.split('@')[1]
        self.timeout = timeout
        self.threads = threads
        self.output = output
        self.results = {
            'email': self.email,
            'username': self.username,
            'domain': self.domain,
            'scan_time': datetime.now().isoformat(),
            'confirmed': [],
            'false_positive': [],
            'breaches': [],
            'gravatar': None
        }
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def print_banner(self):
        print(f"\n{G}{'='*50}{X}")
        print(f"{G}Email2Profile v3.0 - Low False Positive{X}")
        print(f"{C}Email: {self.email}{X}")
        print(f"{C}Username: {self.username}{X}")
        print(f"{C}Domain: {self.domain}{X}")
        print(f"{C}Threads: {self.threads} | Timeout: {self.timeout}s{X}")
        print(f"{G}{'='*50}{X}\n")
    
    def verify_github(self):
        """GitHub verification with multiple checks"""
        url = f"https://api.github.com/users/{self.username}"
        profile_url = f"https://github.com/{self.username}"
        
        try:
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                
                if data.get('login') == self.username and data.get('type') == 'User':
                    return {
                        'platform': 'GitHub',
                        'status': 'confirmed',
                        'url': profile_url,
                        'details': {
                            'name': data.get('name'),
                            'public_repos': data.get('public_repos'),
                            'followers': data.get('followers'),
                            'created_at': data.get('created_at'),
                            'bio': data.get('bio')
                        }
                    }
            elif resp.status_code == 404:
                return {'platform': 'GitHub', 'status': 'not_found'}
            elif resp.status_code == 403:
                return {'platform': 'GitHub', 'status': 'rate_limited'}
        except:
            pass
        return {'platform': 'GitHub', 'status': 'not_found'}
    
    def verify_gitlab(self):
        """GitLab verification"""
        url = f"https://gitlab.com/api/v4/users?username={self.username}"
        
        try:
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    user = data[0]
                    if user.get('username') == self.username:
                        return {
                            'platform': 'GitLab',
                            'status': 'confirmed',
                            'url': user.get('web_url'),
                            'details': {
                                'name': user.get('name'),
                                'public_projects': user.get('public_projects')
                            }
                        }
        except:
            pass
        return {'platform': 'GitLab', 'status': 'not_found'}
    
    def verify_bitbucket(self):
        """BitBucket verification"""
        url = f"https://api.bitbucket.org/2.0/users/{self.username}"
        
        try:
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('username') == self.username:
                    return {
                        'platform': 'Bitbucket',
                        'status': 'confirmed',
                        'url': data.get('links', {}).get('html', {}).get('href'),
                        'details': {
                            'display_name': data.get('display_name')
                        }
                    }
        except:
            pass
        return {'platform': 'Bitbucket', 'status': 'not_found'}
    
    def verify_reddit(self):
        """Reddit verification with ban check"""
        url = f"https://www.reddit.com/user/{self.username}/about.json"
        
        try:
            resp = self.session.get(url, timeout=self.timeout, 
                                   headers={'User-Agent': 'Mozilla/5.0'})
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('kind') == 't2':
                    user_data = data.get('data', {})
                    if user_data.get('name') == self.username:
                        if not user_data.get('is_suspended', False):
                            return {
                                'platform': 'Reddit',
                                'status': 'confirmed',
                                'url': f"https://www.reddit.com/user/{self.username}",
                                'details': {
                                    'comment_karma': user_data.get('comment_karma'),
                                    'post_karma': user_data.get('post_karma'),
                                    'created_utc': user_data.get('created_utc')
                                }
                            }
                        else:
                            return {'platform': 'Reddit', 'status': 'suspended'}
            elif 'banned' in resp.text.lower():
                return {'platform': 'Reddit', 'status': 'banned'}
        except:
            pass
        return {'platform': 'Reddit', 'status': 'not_found'}
    
    def verify_hackernews(self):
        """HackerNews verification"""
        url = f"https://hacker-news.firebaseio.com/v0/user/{self.username}.json"
        
        try:
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200 and resp.text != 'null':
                data = resp.json()
                if data and data.get('id') == self.username:
                    if data.get('karma', 0) > 0 or data.get('created'):
                        return {
                            'platform': 'HackerNews',
                            'status': 'confirmed',
                            'url': f"https://news.ycombinator.com/user?id={self.username}",
                            'details': {
                                'karma': data.get('karma', 0),
                                'created': data.get('created')
                            }
                        }
        except:
            pass
        return {'platform': 'HackerNews', 'status': 'not_found'}
    
    def verify_keybase(self):
        """Keybase verification"""
        url = f"https://keybase.io/_/api/1.0/user/lookup.json?usernames={self.username}"
        
        try:
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('them') and len(data['them']) > 0:
                    user = data['them'][0]
                    if user.get('basics', {}).get('username') == self.username:
                        return {
                            'platform': 'Keybase',
                            'status': 'confirmed',
                            'url': f"https://keybase.io/{self.username}",
                            'details': {
                                'full_name': user.get('basics', {}).get('full_name')
                            }
                        }
        except:
            pass
        return {'platform': 'Keybase', 'status': 'not_found'}
    
    def verify_medium(self):
        """Medium verification - strict check"""
        url = f"https://medium.com/@{self.username}"
        
        try:
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200:
                content = resp.text.lower()
                false_indicators = [
                    'page not found',
                    'no such user',
                    'this page could not be found',
                    'nothing here'
                ]
                for indicator in false_indicators:
                    if indicator in content:
                        return {'platform': 'Medium', 'status': 'not_found'}
                
                if 'follow' in content and 'posts' in content:
                    return {
                        'platform': 'Medium',
                        'status': 'confirmed',
                        'url': url
                    }
        except:
            pass
        return {'platform': 'Medium', 'status': 'not_found'}
    
    def verify_devto(self):
        """Dev.to verification"""
        url = f"https://dev.to/{self.username}"
        
        try:
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200:
                content = resp.text.lower()
                if 'page not found' in content or 'oops' in content:
                    return {'platform': 'Dev.to', 'status': 'not_found'}
                
                if 'posts' in content or 'articles' in content:
                    return {
                        'platform': 'Dev.to',
                        'status': 'confirmed',
                        'url': url
                    }
        except:
            pass
        return {'platform': 'Dev.to', 'status': 'not_found'}
    
    def verify_stackoverflow(self):
        """StackOverflow verification"""
        url = f"https://api.stackexchange.com/2.3/users?inname={self.username}&site=stackoverflow"
        
        try:
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get('items', []):
                    if item.get('display_name', '').lower() == self.username.lower():
                        if item.get('reputation', 0) > 0:
                            return {
                                'platform': 'StackOverflow',
                                'status': 'confirmed',
                                'url': item.get('link'),
                                'details': {
                                    'reputation': item.get('reputation'),
                                    'badges': item.get('badge_counts')
                                }
                            }
        except:
            pass
        return {'platform': 'StackOverflow', 'status': 'not_found'}
    
    def verify_gravatar(self):
        """Gravatar verification"""
        try:
            email_hash = hashlib.md5(self.email.lower().encode()).hexdigest()
            url = f"https://www.gravatar.com/{email_hash}.json"
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                entry = data.get('entry', [{}])[0]
                if entry.get('displayName') or entry.get('profileUrl'):
                    self.results['gravatar'] = {
                        'display_name': entry.get('displayName'),
                        'profile_url': entry.get('profileUrl')
                    }
                    return True
        except:
            pass
        return False
    
    def check_breaches(self):
        """HaveIBeenPwned check"""
        try:
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{self.email}"
            resp = self.session.get(url, timeout=self.timeout)
            
            if resp.status_code == 200:
                breaches = resp.json()
                for breach in breaches:
                    self.results['breaches'].append({
                        'name': breach.get('Name'),
                        'title': breach.get('Title'),
                        'date': breach.get('BreachDate'),
                        'data_classes': breach.get('DataClasses', [])[:3]
                    })
                return True
        except:
            pass
        return False
    
    def run_verification(self):
        """Run all platform verifications"""
        checks = [
            self.verify_github,
            self.verify_gitlab,
            self.verify_bitbucket,
            self.verify_reddit,
            self.verify_hackernews,
            self.verify_keybase,
            self.verify_medium,
            self.verify_devto,
            self.verify_stackoverflow
        ]
        
        print(f"{C}[*] Verifying {len(checks)} platforms (strict mode)...{X}\n")
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = [executor.submit(check) for check in checks]
            
            for future in as_completed(futures):
                result = future.result()
                platform = result.get('platform')
                status = result.get('status')
                
                if status == 'confirmed':
                    self.results['confirmed'].append(result)
                    print(f"{G}[+] {platform}: CONFIRMED - {result.get('url')}{X}")
                elif status == 'not_found':
                    print(f"{R}[-] {platform}: Not found{X}")
                elif status == 'suspended':
                    print(f"{Y}[!] {platform}: Account suspended{X}")
                elif status == 'banned':
                    print(f"{Y}[!] {platform}: Account banned{X}")
                elif status == 'rate_limited':
                    print(f"{Y}[!] {platform}: Rate limited, try again later{X}")
        
        self.verify_gravatar()
        self.check_breaches()
    
    def print_results(self):
        print(f"\n{G}{'='*50}{X}")
        print(f"{G}FINAL RESULTS - {self.email}{X}")
        print(f"{G}{'='*50}{X}")
        
        print(f"\n{C}Username: {self.username}{X}")
        print(f"{C}Domain: {self.domain}{X}")
        
        if self.results['gravatar']:
            print(f"\n{G}[>] Gravatar Profile Found:{X}")
            if self.results['gravatar'].get('display_name'):
                print(f"    Name: {self.results['gravatar']['display_name']}")
        
        confirmed = self.results['confirmed']
        if confirmed:
            print(f"\n{G}[>] CONFIRMED ACCOUNTS ({len(confirmed)}):{X}")
            for acc in confirmed:
                print(f"    {G}+{X} {acc['platform']}: {acc['url']}")
                if 'details' in acc and acc['details']:
                    if 'followers' in acc['details']:
                        print(f"       Followers: {acc['details']['followers']}")
                    if 'reputation' in acc['details']:
                        print(f"       Reputation: {acc['details']['reputation']}")
        else:
            print(f"\n{Y}[!] No confirmed accounts found{X}")
        
        if self.results['breaches']:
            print(f"\n{R}[!] Found in {len(self.results['breaches'])} data breaches:{X}")
            for breach in self.results['breaches'][:5]:
                print(f"    {R}-{X} {breach['title']} ({breach['date']})")
        
        print(f"\n{G}{'='*50}{X}")
    
    def save_results(self):
        filename = self.output if self.output else f"{self.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output_data = {
            'email': self.email,
            'username': self.username,
            'domain': self.domain,
            'scan_time': self.results['scan_time'],
            'confirmed_accounts': self.results['confirmed'],
            'breaches': self.results['breaches'],
            'gravatar': self.results['gravatar']
        }
        
        with open(filename, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"\n{G}[+] Results saved to: {filename}{X}")
    
    def run(self):
        self.print_banner()
        start = time.time()
        
        self.run_verification()
        self.print_results()
        
        elapsed = time.time() - start
        print(f"{C}[+] Scan completed in {elapsed:.2f} seconds{X}")
        
        self.save_results()

def main():
    parser = argparse.ArgumentParser(description='Email2Profile - Low False Positive Version')
    parser.add_argument('-e', '--email', required=True, help='Target email address')
    parser.add_argument('-t', '--threads', type=int, default=5, help='Threads (default: 5)')
    parser.add_argument('-to', '--timeout', type=int, default=15, help='Timeout seconds (default: 15)')
    parser.add_argument('-o', '--output', help='Output JSON file')
    
    args = parser.parse_args()
    
    if not args.email or '@' not in args.email:
        print(f"{R}Error: Valid email required (user@domain.com){X}")
        sys.exit(1)
    
    scanner = Email2Profile(
        email=args.email,
        timeout=args.timeout,
        threads=args.threads,
        output=args.output
    )
    
    try:
        scanner.run()
    except KeyboardInterrupt:
        print(f"\n{Y}[!] Interrupted by user{X}")
        sys.exit(0)
    except Exception as e:
        print(f"{R}[!] Error: {e}{X}")
        sys.exit(1)

if __name__ == "__main__":
    main()
