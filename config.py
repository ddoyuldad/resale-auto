"""
=== 매입 자동화 프로그램 설정 ===
API 키는 .env 파일에 저장하세요. (GitHub에는 올라가지 않습니다)
"""
import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일에서 환경변수 자동 로드

# ── 네이버 쇼핑 검색 API ──────────────────────────────────
# 발급: https://developers.naver.com/apps
NAVER_CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

# ── Claude AI (사용 안 함 — AI 분류는 Gemini로 대체됨) ──────
# 발급: https://console.anthropic.com/
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── 쿠팡 OPEN API (선택사항) ──────────────────────────────
# 발급: 쿠팡 Wing → OPEN API 키 발급
COUPANG_ACCESS_KEY = os.environ.get("COUPANG_ACCESS_KEY", "")
COUPANG_SECRET_KEY = os.environ.get("COUPANG_SECRET_KEY", "")
COUPANG_VENDOR_ID  = os.environ.get("COUPANG_VENDOR_ID", "")

# ── Google Gemini API (이미지 자동 분류 + 상세페이지 생성) ────
# 무료 발급: https://aistudio.google.com/apikey
# 없으면 빈 문자열("") → 수동 분류 모드로 전환됩니다.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ── 프로그램 설정 ─────────────────────────────────────────
THUMBNAIL_SIZE     = 130          # 엑셀 썸네일 크기 (px)
NAVER_DISPLAY      = 20           # 네이버 검색 결과 수 (1페이지)
DETAIL_PAGE_WIDTH  = 860          # 상세페이지 이미지 폭 (px)
