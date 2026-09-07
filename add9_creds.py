# -*- coding: utf-8 -*-
"""서비스 계정 자격증명 로더 — 로컬(키 파일) / 클라우드(환경변수 JSON) 양쪽 지원.

우선순위:
  1) 환경변수 ADD9_SA_JSON  = 서비스 계정 JSON 전체 문자열  (클라우드 루틴용)
  2) 환경변수 ADD9_SA_CRED  = 키 파일 절대경로
  3) C:\\BeautyDesk\\credentials\\service-account.json         (집 PC)
  4) ~/.add9/service-account.json                             (그 외 PC)

키 파일은 저장소·OneDrive에 두지 않는다. .gitignore가 *.json 을 막는다.
"""
import os
import sys
import json
import pathlib

DEFAULT_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

_FILE_CANDS = [
    os.environ.get('ADD9_SA_CRED'),
    r'C:\BeautyDesk\credentials\service-account.json',
    str(pathlib.Path.home() / '.add9' / 'service-account.json'),
]


def _info_or_path():
    raw = os.environ.get('ADD9_SA_JSON')
    if raw:
        try:
            return ('info', json.loads(raw))
        except Exception as e:
            sys.exit(f'중단: ADD9_SA_JSON 환경변수 JSON 파싱 실패 — {e}')
    for c in _FILE_CANDS:
        if c and pathlib.Path(c).is_file():
            return ('file', c)
    sys.exit('중단: 서비스 계정 자격증명을 찾지 못했습니다.\n'
             '  클라우드: 환경변수 ADD9_SA_JSON 에 서비스 계정 JSON 전체\n'
             '  로컬: ' + ' 또는 '.join(x for x in _FILE_CANDS if x))


def get_credentials(scopes=None):
    """google.oauth2.service_account.Credentials 객체를 돌려준다."""
    from google.oauth2.service_account import Credentials
    kind, val = _info_or_path()
    scopes = scopes or DEFAULT_SCOPES
    if kind == 'info':
        return Credentials.from_service_account_info(val, scopes=scopes)
    return Credentials.from_service_account_file(val, scopes=scopes)


def get_gspread_client():
    """인증된 gspread 클라이언트를 돌려준다."""
    import gspread
    return gspread.authorize(get_credentials())
