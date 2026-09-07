# -*- coding: utf-8 -*-
"""P1_시장뷰_시안 행높이 맞추기 — 회차 반영 뒤에 실행한다.

왜 필요한가
  central_desk_round.py는 플레이북 §1에 따라 P1의 행높이를 건드리지 않는다.
  그래서 새 회차 본문이 이전보다 길면 폰에서 카드 아래가 잘린다.
  (2026-09-05 실측: 9/5 회차 반영 뒤 21개 행이 부족한 상태였다.)

왜 autofit을 쓰지 않는가
  Sheets API의 autoResizeDimensions는 **wrap된 텍스트를 한 줄로 계산**한다.
  2026-09-04에 이걸 썼다가 12개 행이 20px로 붕괴해 스냅샷 롤백했다. 절대 쓰지 말 것.
  대신 글자폭(동아시아 전각=1.0em / 그 외=0.55em) × 열폭으로 필요한 줄 수를 직접 센다.

사용
  python central_desk_fit_heights.py           # 드라이런(변경 없음)
  python central_desk_fit_heights.py --apply

자격증명: add9_creds.get_credentials() — 로컬 파일 또는 ADD9_SA_JSON 환경변수.
"""
import sys
import math
import unicodedata

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import gspread
from googleapiclient.discovery import build

from add9_creds import get_credentials

SID = '1N28JERpj9Es4eTPUO_nGMYWwvRfeXQTfg72BChQEI6Q'
TAB = 'P1_시장뷰_시안'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 폰 세로 화면 기준 여유. 1.0이면 PC에선 맞고 폰에선 줄바꿈이 늘어 잘린다.
SLACK = 1.30


# (행, 글자크기, 본문 폭px) — 폭은 B:C 병합이면 337, B 단독이면 287
def plan():
    p = []
    for t, c, d in ((7, 8, 9), (10, 11, 12), (13, 14, 15)):      # 해외신호: 제목/한줄결론/상세
        p += [(t, 11, 287), (c, 11, 337), (d, 10, 337)]
    for b in (19, 28, 37):                                        # 제품: 한줄추천~주의점
        p += [(b + k, 10, 337) for k in (2, 3, 4, 5, 6)]
    for t, g in ((49, 50), (52, 53), (55, 56)):                   # 콘텐츠: 제목/한줄기획
        p += [(t, 11, 287), (g, 10, 287)]
    return p


def visual_width(s, fs):
    return sum(fs * (1.0 if unicodedata.east_asian_width(ch) in ('W', 'F') else 0.55) for ch in s)


def needed_px(text, width, fs):
    usable = width - 18                       # 좌우 패딩
    lines = 0
    for seg in text.split('\n'):
        lines += 1 if not seg else max(1, math.ceil(visual_width(seg, fs) / usable))
    return max(26, math.ceil(math.ceil(lines * (fs * 1.55 + 2)) * SLACK) + 12)


def main(apply_):
    creds = get_credentials(SCOPES)
    svc = build('sheets', 'v4', credentials=creds)
    sh = gspread.authorize(creds).open_by_key(SID)
    ws = sh.worksheet(TAB)

    meta = svc.spreadsheets().get(spreadsheetId=SID, ranges=[TAB],
        fields='sheets(properties(sheetId),data(rowMetadata(pixelSize)))').execute()['sheets'][0]
    gid = meta['properties']['sheetId']
    cur = [rm.get('pixelSize') for rm in meta['data'][0]['rowMetadata']]

    vals = ws.get('A1:C60')

    def cell(r):
        return vals[r - 1][1] if len(vals) >= r and len(vals[r - 1]) > 1 else ''

    reqs, rep = [], []
    for r, fs, w in plan():
        px = needed_px(cell(r), w, fs)
        old = cur[r - 1] if r - 1 < len(cur) else None
        if old != px:
            reqs.append({'updateDimensionProperties': {
                'range': {'sheetId': gid, 'dimension': 'ROWS', 'startIndex': r - 1, 'endIndex': r},
                'properties': {'pixelSize': px}, 'fields': 'pixelSize'}})
            rep.append((r, old, px, len(cell(r))))

    if not rep:
        print('행높이 이상 없음. 변경할 것 없습니다.')
        return
    print('%-5s %-9s %-9s %s' % ('행', '현재', '필요', '글자'))
    for r, old, px, n in rep:
        mark = '  ← 잘림' if (old or 0) < px else ''
        print('%-5d %-9s %-9s %d자%s' % (r, str(old) + 'px', str(px) + 'px', n, mark))
    if not apply_:
        print('\n드라이런. --apply 로 반영')
        return
    svc.spreadsheets().batchUpdate(spreadsheetId=SID, body={'requests': reqs}).execute()
    print('\n%d개 행 반영 완료' % len(rep))


if __name__ == '__main__':
    main('--apply' in sys.argv)
