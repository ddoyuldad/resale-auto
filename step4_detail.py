"""
STEP 4 — 쿠팡/네이버 상세페이지 AI 이미지 자동 생성 v2.0
========================================================
제품 사진 → AI 분석 → 누끼컷 → 배경합성 → 상세페이지 12장 자동 생성

모델 옵션:
  1. 나노바나나     (무료, 하루 ~500장)  — gemini-2.5-flash-image
  2. 나노바나나2    (유료, ~60원/장)     — gemini-3.1-flash-image-preview  ⭐추천
  3. 나노바나나 Pro (유료, ~180원/장)    — gemini-3-pro-image-preview
  4. Imagen 4 Fast (유료, ~27원/장)     — imagen-4.0-generate-001 (편집불가)

필요 설치: pip install google-genai Pillow
"""
import os, sys, json, time, glob, re
import urllib.request, urllib.parse
from pathlib import Path
from io import BytesIO
from datetime import datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from PIL import Image, ImageOps

# ─── config에서 키 가져오기 ──────────────────────────────
try:
    from config import GEMINI_API_KEY, DETAIL_PAGE_WIDTH
    from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
except ImportError:
    GEMINI_API_KEY = ""
    DETAIL_PAGE_WIDTH = 860
    NAVER_CLIENT_ID = ""
    NAVER_CLIENT_SECRET = ""

# ═══════════════════════════════════════════════════════════
# 모델 목록
# ═══════════════════════════════════════════════════════════
MODELS = [
    {
        "no": 1,
        "name": "나노바나나 (Nano Banana)",
        "id": "gemini-2.5-flash-image",
        "free": True,
        "price": "무료 (하루 ~500장)",
        "cost_per_img": 0,
        "quality": "★★★☆☆",
        "speed": "★★★★★",
        "desc": "무료! 가성비 최고. 기본 품질. 빠른 속도.",
        "text_model": "gemini-2.5-flash",
    },
    {
        "no": 2,
        "name": "나노바나나2 (Nano Banana 2) ⭐추천",
        "id": "gemini-3.1-flash-image-preview",
        "free": False,
        "price": "~60원/장 (1K) | ~90원/장 (2K)",
        "cost_per_img": 0.045,
        "quality": "★★★★☆",
        "speed": "★★★★☆",
        "desc": "고품질+빠름. 텍스트 렌더링 우수. 4K지원.",
        "text_model": "gemini-3-flash-preview",
    },
    {
        "no": 3,
        "name": "나노바나나 Pro (Nano Banana Pro)",
        "id": "gemini-3-pro-image-preview",
        "free": False,
        "price": "~180원/장 (2K) | ~320원/장 (4K)",
        "cost_per_img": 0.134,
        "quality": "★★★★★",
        "speed": "★★★☆☆",
        "desc": "최고 품질. 텍스트 정확도 최상. 느림.",
        "text_model": "gemini-3-pro-preview",
    },
    {
        "no": 4,
        "name": "Imagen 4 Fast (텍스트→이미지 전용)",
        "id": "imagen-4.0-generate-001",
        "free": False,
        "price": "~27원/장 ($0.02) 최저가",
        "cost_per_img": 0.02,
        "quality": "★★★☆☆",
        "speed": "★★★★★",
        "desc": "최저가. 이미지편집 불가. 누끼컷 불가.",
        "text_model": "gemini-2.5-flash",
        "text_only": True,
    },
]

# ─── 기본 설정 ──────────────────────────────────────────
DETAIL_RATIO = "3:4"
SQUARE_RATIO = "1:1"
RESOLUTION = "1K"
WAIT_SEC = 3

# ─── 카테고리별 배경 설명 ────────────────────────────────
CATEGORY_BACKGROUNDS = {
    "식품": "깨끗한 대리석 주방 카운터 위, 나무 도마, 창문에서 들어오는 따뜻한 자연광, 신선한 허브 소품",
    "건강기능식품": "고급 다크우드 테이블 위, 은은한 간접조명과 제품에 스포트라이트, 프리미엄 분위기",
    "음료": "아늑한 카페 테이블, 아침 햇살, 차분하고 리프레시한 분위기",
    "건강음료": "아늑한 카페 테이블, 아침 햇살, 차분하고 리프레시한 분위기",
    "과자": "밝은 파스텔 배경, 팝한 색감, 활기찬 조명, 파티 분위기",
    "생활용품": "화이트톤 깨끗한 거실 테이블, 미니멀하고 청결한 분위기, 관엽식물 소품",
    "생활용품/세정제": "화이트톤 깨끗한 거실 테이블, 미니멀하고 청결한 분위기, 관엽식물 소품",
    "생활용품/세척제": "화이트톤 깨끗한 거실 테이블, 미니멀하고 청결한 분위기, 관엽식물 소품",
    "주방용품": "모던 인테리어 주방, 요리 중인 장면, 따뜻한 가정 분위기",
    "미용": "대리석 화장대 위, 꽃과 소프트 핑크 톤, 글로우 조명, 고급 질감",
    "헤어케어": "대리석 화장대 위, 꽃과 소프트 핑크 톤, 글로우 조명, 고급 질감",
    "헤어케어/샴푸": "대리석 화장대 위, 꽃과 소프트 핑크 톤, 글로우 조명, 고급 질감",
    "반려동물": "따뜻한 거실 바닥, 반려동물이 함께 있는 일상적이고 따뜻한 분위기",
    "기타": "깔끔한 화이트 스튜디오 배경, 소프트박스 조명, 프로페셔널 촬영 분위기",
}


# ─── 네이버 검색으로 제품 정보 보충 ─────────────────────
def search_product_info_online(product_name, brand=""):
    """네이버 쇼핑 API로 제품 정보를 검색해서 보충 정보를 반환"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return {}

    query = f"{brand} {product_name}".strip() if brand else product_name
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/shop.json?query={encoded}&display=5&sort=sim"

    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        items = data.get("items", [])
        if not items:
            return {}

        # 상위 결과에서 정보 추출
        extra_info = {
            "search_titles": [],
            "price_range": "",
            "categories": [],
            "mall_names": [],
        }

        prices = []
        for item in items[:5]:
            title = re.sub(r"<[^>]+>", "", item.get("title", ""))
            extra_info["search_titles"].append(title)
            try:
                price = int(item.get("lprice", 0))
                if price > 0:
                    prices.append(price)
            except (ValueError, TypeError):
                pass
            cat = item.get("category1", "")
            if cat and cat not in extra_info["categories"]:
                extra_info["categories"].append(cat)
            mall = item.get("mallName", "")
            if mall and mall not in extra_info["mall_names"]:
                extra_info["mall_names"].append(mall)

        if prices:
            extra_info["price_range"] = f"{min(prices):,}원 ~ {max(prices):,}원"
            extra_info["lowest_price"] = min(prices)

        return extra_info
    except Exception:
        return {}


def get_model_by_no(no):
    """모델 번호로 모델 딕셔너리 반환"""
    for m in MODELS:
        if m["no"] == no:
            return m
    return MODELS[0]


def get_background_for_category(category):
    """카테고리에 맞는 배경 설명 반환"""
    if category in CATEGORY_BACKGROUNDS:
        return CATEGORY_BACKGROUNDS[category]
    # 부분 매칭
    for key, val in CATEGORY_BACKGROUNDS.items():
        if key in category or category in key:
            return val
    return CATEGORY_BACKGROUNDS["기타"]


# ═══════════════════════════════════════════════════════════
# 상세페이지 생성기 클래스
# ═══════════════════════════════════════════════════════════
class DetailPageGenerator:
    def __init__(self, api_key=None, model=None, progress_callback=None):
        """
        Args:
            api_key: Gemini API 키 (없으면 config.py / 환경변수 / .env에서 탐색)
            model: 모델 딕셔너리 (MODELS 리스트의 항목). 기본값=MODELS[0]
            progress_callback: 진행 상황 콜백 함수 fn(message, progress_pct)
        """
        key = api_key or GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        # .env 파일 탐색
        if not key:
            for env_path in [Path(".env"), Path(__file__).parent / ".env"]:
                if env_path.exists():
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        if k.strip() in ("GEMINI_API_KEY", "GOOGLE_API_KEY") and v:
                            key = v
                            break
                if key:
                    break

        if not key:
            raise ValueError(
                "Gemini API 키가 필요합니다.\n"
                "   config.py에 GEMINI_API_KEY = 'your_key'\n"
                "   또는 .env 파일에 GEMINI_API_KEY=your_key\n"
                "   무료 발급: https://aistudio.google.com/apikey"
            )

        if genai is None:
            raise ImportError("google-genai 패키지가 필요합니다: pip install google-genai")

        self.client = genai.Client(api_key=key)
        self.model = model or MODELS[0]
        self.image_model = self.model["id"]
        self.text_model = self.model.get("text_model", "gemini-2.5-flash")
        self.is_text_only = self.model.get("text_only", False)
        self.product_info = {}
        self.output_dir = None
        self.generated_count = 0
        self.progress_callback = progress_callback or (lambda msg, pct: print(msg))

    def _log(self, msg, pct=None):
        self.progress_callback(msg, pct)

    # ── 제품 분석 ────────────────────────────────────────
    def analyze_product(self, images, product_name="", existing_info=None):
        """
        제품 이미지를 분석해서 상세페이지 기획 정보 추출
        existing_info가 있으면 기존 분석 결과를 활용
        """
        self._log("🔍 STEP 0: 제품 분석 중...")

        # 기존 분석 정보가 있으면 활용
        if existing_info:
            product_name = existing_info.get("product_name", product_name) or product_name
            brand = existing_info.get("brand", "")
            category = existing_info.get("category", "기타")
            feature = existing_info.get("feature", "")
            selling_point = existing_info.get("selling_point", "")
        else:
            brand, category, feature, selling_point = "", "기타", "", ""

        # 네이버 검색으로 보충 정보 수집
        self._log("   🔍 네이버에서 제품 정보 검색 중...")
        online_info = search_product_info_online(product_name, brand)
        online_context = ""
        if online_info:
            titles = online_info.get("search_titles", [])
            price_range = online_info.get("price_range", "")
            cats = online_info.get("categories", [])
            if titles:
                online_context += f"\n온라인 판매명 참고: {' / '.join(titles[:3])}"
            if price_range:
                online_context += f"\n온라인 가격대: {price_range}"
            if cats:
                online_context += f"\n온라인 카테고리: {', '.join(cats)}"
            self._log(f"   ✅ 검색 정보 {len(titles)}건 확보")
        else:
            self._log("   ⚠️ 검색 정보 없음 (사진 기반으로 진행)")

        prompt = f"""너는 쿠팡/네이버 스마트스토어 전문 상세페이지 기획자야.
첨부한 제품 사진들을 분석하고 상세페이지 기획을 해줘.
{"상품명: " + product_name if product_name else "상품명을 사진에서 읽어서 파악해줘."}
{"브랜드: " + brand if brand else ""}
{"카테고리: " + category if category else ""}
{"제품특징: " + feature if feature else ""}
{"셀링포인트: " + selling_point if selling_point else ""}
{online_context}

반드시 아래 JSON만 출력. 다른 텍스트 금지:
{{"productName":"제품명","brand":"브랜드","category":"식품/건강기능식품/음료/과자/생활용품/주방용품/미용/반려동물/기타 중 택1","price":"가격대","description":"한줄설명(20자)","targetCustomer":"타겟","sellingPoints":["SP1","SP2","SP3"],"hookingMents":["후킹1(15자)","후킹2","후킹3","후킹4","후킹5"],"painPoints":["고민1(20자)","고민2","고민3"],"features":[{{"title":"5자","mainCopy":"15자","subCopy":"25자"}},{{"title":"5자","mainCopy":"15자","subCopy":"25자"}},{{"title":"5자","mainCopy":"15자","subCopy":"25자"}}],"usageTips":["활용1","활용2","활용3","활용4"],"specs":"스펙요약","priceCompare":"가성비(15자)","ctaCopy":"CTA(15자)"}}"""

        try:
            resp = self.client.models.generate_content(
                model=self.text_model,
                contents=[prompt] + images[:5],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            info = json.loads(text)
            self.product_info = info
            self._log(f"   ✅ 제품명: {info.get('productName', '?')}")
            self._log(f"   ✅ 브랜드: {info.get('brand', '?')}")
            self._log(f"   ✅ 카테고리: {info.get('category', '?')}")
            self._log(f"   ✅ 후킹멘트: {info.get('hookingMents', ['?'])[0]}")
            return info
        except Exception as e:
            self._log(f"   ⚠️ AI 분석 실패: {e} → 기존 정보 + 기본 템플릿 사용")
            self.product_info = {
                "productName": product_name or "제품",
                "brand": brand,
                "category": category,
                "description": feature or "고품질 제품",
                "hookingMents": ["이 가격에 이 퀄리티?", "한정수량 긴급입고", "100만개 팔린 이유", "아직도 이거 모르세요?", "오늘만 이 가격"],
                "painPoints": ["매번 고민되는 선택", "품질 확인 어려움", "가격 부담"],
                "features": [
                    {"title": "품질", "mainCopy": "프리미엄 품질", "subCopy": "엄선된 원료로 만든 제품"},
                    {"title": "가성비", "mainCopy": "가성비 끝판왕", "subCopy": "합리적인 가격으로 만족"},
                    {"title": "안전", "mainCopy": "검증된 안전성", "subCopy": "까다로운 기준 통과"}
                ],
                "usageTips": ["일상 활용", "특별한 날", "선물용", "대량 구매"],
                "specs": existing_info.get("spec", "상세 스펙 참고") if existing_info else "스펙 참고",
                "priceCompare": "마트대비 초특가",
                "ctaCopy": "지금 장바구니 담기 🛒",
            }
            return self.product_info

    # ── 이미지 생성 (공통) ────────────────────────────────
    def _gen_image(self, contents, ratio=DETAIL_RATIO, fname="out.png", retries=2):
        for attempt in range(retries + 1):
            try:
                cfg = {
                    "response_modalities": ["TEXT", "IMAGE"],
                    "image_config": types.ImageConfig(aspect_ratio=ratio),
                }
                if RESOLUTION != "1K":
                    cfg["image_config"] = types.ImageConfig(aspect_ratio=ratio, image_size=RESOLUTION)

                resp = self.client.models.generate_content(
                    model=self.image_model,
                    contents=contents,
                    config=types.GenerateContentConfig(**cfg),
                )
                for part in resp.candidates[0].content.parts:
                    img = None
                    if hasattr(part, "inline_data") and part.inline_data:
                        img = Image.open(BytesIO(part.inline_data.data))
                    elif hasattr(part, "as_image"):
                        try:
                            img = part.as_image()
                        except Exception:
                            pass
                    if img:
                        path = self.output_dir / fname
                        img.save(path, quality=95)
                        self.generated_count += 1
                        self._log(f"   💾 저장: {fname}")
                        return path

                if attempt < retries:
                    self._log(f"   ⚠️ 이미지 없음, 재시도 {attempt+1}/{retries}...")
                    time.sleep(WAIT_SEC)
                else:
                    self._log(f"   ❌ 실패: {fname}")
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RATE" in err_str.upper():
                    w = WAIT_SEC * (attempt + 3)
                    self._log(f"   ⏳ 속도 제한 → {w}초 대기...")
                    time.sleep(w)
                elif attempt < retries:
                    self._log(f"   ⚠️ {e}, 재시도...")
                    time.sleep(WAIT_SEC * 2)
                else:
                    self._log(f"   ❌ 실패: {fname} - {e}")
        return None

    # ── 누끼컷 생성 ─────────────────────────────────────
    def gen_nukki(self, images):
        self._log("\n🎯 STEP 1: 누끼컷 생성 중...")
        if self.is_text_only:
            self._log("   ⚠️ 이 모델은 이미지 편집 불가 → 건너뜀")
            return []

        info = self.product_info
        name = info.get("productName", "제품")
        brand = info.get("brand", "")
        paths = []

        for i, img in enumerate(images[:3]):
            p = f"""이 {name} 사진에서 배경을 완전히 제거하고 제품만 추출.
- 순백색(#FFFFFF) 배경, 라벨/텍스트/색상 원본 유지
- {brand} 로고 절대 변경 금지, 가장자리 자연스럽게, 그림자 제거
- 중앙 배치, 스튜디오 촬영처럼, 외관 수정 금지 배경만 변경"""
            r = self._gen_image([p, img], SQUARE_RATIO, f"00_nukki_{i+1}.png")
            if r:
                paths.append(r)
            time.sleep(WAIT_SEC)

        return paths

    # ── 누끼컷 1장만 생성 (간소화) ───────────────────────
    def gen_nukki_single(self, images):
        """누끼컷 1장만 생성 (간소화 버전)"""
        self._log("\n🎯 STEP 1: 누끼컷 생성 중...")
        if self.is_text_only:
            self._log("   ⚠️ 이 모델은 이미지 편집 불가 → 건너뜀")
            return None

        info = self.product_info
        name = info.get("productName", "제품")
        brand = info.get("brand", "")

        # 가장 좋은 이미지 선택 (1/3 지점)
        idx = min(len(images) // 3, len(images) - 1)
        img = images[idx]

        p = f"""이 {name} 사진에서 배경을 완전히 제거하고 제품만 추출.
- 순백색(#FFFFFF) 배경, 라벨/텍스트/색상 원본 유지
- {brand} 로고 절대 변경 금지, 가장자리 자연스럽게, 그림자 제거
- 중앙 배치, 스튜디오 촬영처럼, 외관 수정 금지 배경만 변경"""
        result = self._gen_image([p, img], SQUARE_RATIO, "00_nukki.png")
        return result

    # ── 라이프스타일 배경 합성 ────────────────────────────
    def gen_lifestyle(self, nukki_img):
        self._log("\n🌿 STEP 2: 라이프스타일 배경 합성 중...")
        if self.is_text_only:
            self._log("   ⚠️ 이 모델은 편집 불가 → 건너뜀")
            return None

        info = self.product_info
        name = info.get("productName", "제품")
        brand = info.get("brand", "")
        bg = get_background_for_category(info.get("category", "기타"))

        p = f"""이 {name}을 아래 장면에 자연스럽게 배치.
- 장면: {bg}
- 중앙~우측, 약간 45도 각도, 라벨 원본 100% 유지
- {brand} 로고 변경 금지, 50mm 렌즈 얕은 심도, 비율 유지"""

        return self._gen_image([p, nukki_img], DETAIL_RATIO, "00_lifestyle.png")

    # ── 상세페이지 6~7장 생성 ─────────────────────────────
    def gen_pages(self, images, nukki=None, life=None):
        self._log("\n📄 STEP 2: 상세페이지 6장 생성 중...")
        info = self.product_info
        n = info.get("productName", "제품")
        b = info.get("brand", "")
        bg = get_background_for_category(info.get("category", "기타"))
        h = info.get("hookingMents", ["이 가격에 이 퀄리티?"] * 5)
        pp = info.get("painPoints", ["고민1", "고민2", "고민3"])
        ft = info.get("features", [{"title": "특징", "mainCopy": "품질", "subCopy": "설명"}] * 3)
        sp = info.get("specs", "스펙")
        ds = info.get("description", n)
        ct = info.get("ctaCopy", "구매 🛒")
        price = info.get("price", "")
        ingredients = ""
        usage = ""
        if hasattr(self, '_existing_info') and self._existing_info:
            ingredients = self._existing_info.get("ingredients", "")
            usage = self._existing_info.get("usage", "")
            if not price:
                price = self._existing_info.get("price_tag", "")

        base = nukki or images[0]
        ce = not self.is_text_only

        # ── 6장 페이지 구조 ──
        target = info.get("targetCustomer", "")
        category = info.get("category", "")
        pain0 = pp[0] if pp else ""
        ft0 = ft[0]["mainCopy"] if ft else ""
        ft1 = ft[1]["mainCopy"] if len(ft) > 1 else ""
        # 후킹 핵심 카피: 제품 정체가 명확히 드러나는 문장 생성
        hooking_copy = (
            f"{target}이라면 주목! {n}가 해결합니다"
            if target else
            f"{category} 고민? {n}로 해결하세요"
            if category else h[0]
        )

        pages = [
            # 1. 후킹 — 제품 정체 + 구매욕 자극
            ("01_hooking.png", base if ce else None,
             f"""쿠팡/네이버 상세페이지 최상단 후킹 이미지. 세로 비율 3:4.
소비자가 스크롤을 멈추고 "이게 내게 필요한 제품이다"라고 느끼게 만드는 이미지.

[제품 정보]
- 브랜드: {b}
- 제품명: {n}
- 카테고리: {category}
- 타겟 고객: {target}
- 제품 핵심 설명: {ds}
- 주요 기능: {ft0}{f" / {ft1}" if ft1 else ""}
- 고객 고민 해결: {pain0}
{f"- 가격: {price}" if price else ""}

[레이아웃 — 반드시 준수]
배경: 짙은 다크네이비~블랙 그라데이션. 프리미엄하고 임팩트 있게.

상단 40%: 다음 두 줄 텍스트를 화면 꽉 차게 크고 굵게 표현
  1줄: "{b} {n}" — 이게 어떤 제품인지 핵심을 담은 카피 (한국어, 흰색 굵은 고딕)
  2줄: "{h[0]}" — 노란색 하이라이트 박스 안에 강조 텍스트

중앙~하단 55%: 제품 원본 이미지를 크고 선명하게 배치. 프리미엄 조명 효과.

하단 5%: "{b}" 브랜드명 작게.
{f'가격 강조: "{price}" 빨간색으로 눈에 띄게' if price else ""}

[주의사항]
- {b} 제품 라벨/로고/텍스트 절대 변경·합성 금지. 있는 그대로 보여줄 것.
- 상단 텍스트가 "이 제품이 무엇인지, 왜 나에게 필요한지" 명확히 전달해야 함.
- 범용적인 광고 문구("최고의 선택" 등) 사용 금지. 이 제품만의 특성을 담을 것."""),

            # 2. 제품 소개 — 이름, 브랜드, 핵심 정보
            ("02_intro.png", base if ce else None,
             f"""제품 소개 페이지. 깔끔한 화이트~연크림 배경.
제품: {n} (브랜드: {b})
상단: "{b}" 브랜드명 작게 + "{n}" 제품명 크고 굵게.
중앙: 제품 이미지를 깔끔하게 배치.
하단: "{ds}" 한줄 설명.
{f'핵심 스펙: {sp}' if sp else ''}
깔끔하고 정돈된 느낌. 정보 전달 명확하게. 신뢰감.
{b} 라벨/로고 변경 금지."""),

            # 3. 핵심 특징 3가지
            ("03_features.png", base if ce else None,
             f"""핵심 특징 페이지. 밝은 배경.
제품: {n}
상단: "이 제품이 특별한 이유" 굵은 텍스트.
3가지 특징을 세로로 나열:
✅ {ft[0]['mainCopy']} — {ft[0]['subCopy']}
✅ {ft[1]['mainCopy'] if len(ft)>1 else '프리미엄 품질'} — {ft[1]['subCopy'] if len(ft)>1 else '엄선된 원료'}
✅ {ft[2]['mainCopy'] if len(ft)>2 else '검증된 안전성'} — {ft[2]['subCopy'] if len(ft)>2 else '인증 완료'}
각 항목에 아이콘 또는 체크마크. 텍스트 크고 읽기 쉽게.
좌측에 작은 제품 이미지. {b} 라벨 유지."""),

            # 4. 상세 정보 — 성분/스펙/용법
            ("04_detail.png", base if ce else None,
             f"""상세 정보 인포그래픽 페이지.
제품: {n} (브랜드: {b})
화이트 배경, 정돈된 레이아웃.
상단: "꼼꼼히 확인하세요 📋" 텍스트.
{f'주요 성분: {ingredients}' if ingredients else ''}
{f'용법/용량: {usage}' if usage else ''}
{f'스펙: {sp}' if sp else ''}
표/리스트 형식으로 깔끔하게 정리. 작은 아이콘 활용.
하단에 제품 이미지 작게. 신뢰감 있는 정보 전달."""),

            # 5. 리뷰 + 신뢰 + 배송
            ("05_trust.png", None,
             f"""고객 리뷰 + 신뢰 + 배송안내 통합 페이지.
제품: {n}
상단 50%: "구매자 실제 후기 💬"
3개 리뷰 카드: ⭐⭐⭐⭐⭐ "재구매 의사 100%!" / ⭐⭐⭐⭐⭐ "{n} 정말 좋아요" / ⭐⭐⭐⭐⭐ "가성비 최고 추천합니다"
하단 50%: 배송/교환 안내
🚀 빠른배송 | 🔄 교환/반품 가능 | 💯 정품 보장
아이콘+텍스트 가로 나열. 크림/화이트 배경."""),

            # 6. CTA 마무리
            ("06_cta.png", base if ce else None,
             f"""CTA 마무리 페이지. 어두운 프리미엄 배경 (네이비~블랙 그라데이션).
제품: {n} (브랜드: {b})
상단: "더 이상 고민하지 마세요" 흰색 텍스트.
중앙: 제품 크게 + 골드빛 하이라이트 효과.
하단: "{ct}" 노란색 강조 버튼 스타일.
{f'"지금 {price}에 만나보세요"' if price else ''}
프리미엄+구매욕 자극. {b} 라벨 유지."""),
        ]

        results = []
        for idx, (fname, img, prompt) in enumerate(pages):
            label = fname.split("_", 1)[1].replace(".png", "")
            self._log(f"\n   📸 [{idx+1}/{len(pages)}] {label}")
            contents = [prompt, img] if img else [prompt]
            results.append(self._gen_image(contents, DETAIL_RATIO, fname))
            time.sleep(WAIT_SEC)

        return results

    # ── 제품 사진 갤러리 페이지 (Pillow 직접 생성) ─────────
    def gen_gallery_page(self, image_paths, width=None):
        """실제 제품 사진들을 2열 그리드로 배치한 갤러리 이미지 생성 (AI 미사용)"""
        self._log("\n🖼️ STEP 3: 제품 사진 갤러리 생성 중...")

        target_w = width or DETAIL_PAGE_WIDTH
        col_count = 2
        padding = 16
        cell_w = (target_w - padding * 3) // col_count
        header_h = 80  # 상단 타이틀 영역

        # 사용할 이미지 (최대 8장)
        valid_paths = []
        for p in image_paths:
            if os.path.isfile(p):
                valid_paths.append(p)
            if len(valid_paths) >= 8:
                break

        if not valid_paths:
            self._log("   ⚠️ 갤러리에 넣을 이미지가 없습니다.")
            return None

        # 이미지 로드 & 리사이즈
        cells = []
        for p in valid_paths:
            try:
                img = Image.open(p).convert("RGB")
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
                # 셀 크기에 맞게 리사이즈 (비율 유지, 중앙 크롭)
                ratio = max(cell_w / img.width, cell_w / img.height)
                resized = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
                # 중앙 크롭
                left = (resized.width - cell_w) // 2
                top = (resized.height - cell_w) // 2
                cropped = resized.crop((left, top, left + cell_w, top + cell_w))
                cells.append(cropped)
            except Exception as e:
                self._log(f"   ⚠️ {Path(p).name} 로드 실패: {e}")

        if not cells:
            return None

        # 전체 높이 계산
        rows = (len(cells) + col_count - 1) // col_count
        total_h = header_h + rows * (cell_w + padding) + padding

        # 캔버스 생성 (밝은 회색 배경)
        canvas = Image.new("RGB", (target_w, total_h), (248, 249, 250))

        # 헤더 배경
        header_bg = Image.new("RGB", (target_w, header_h), (27, 42, 74))  # 네이비
        canvas.paste(header_bg, (0, 0))

        # 헤더 텍스트 (PIL로 간단히)
        try:
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(canvas)
            # 시스템 폰트 탐색
            font = None
            font_paths = [
                "C:/Windows/Fonts/malgunbd.ttf",   # 맑은 고딕 Bold
                "C:/Windows/Fonts/malgun.ttf",      # 맑은 고딕
                "C:/Windows/Fonts/gulim.ttc",       # 굴림
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            ]
            for fp in font_paths:
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, 28)
                    break
            if not font:
                font = ImageFont.load_default()

            text = "제품 실물 이미지"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            tx = (target_w - tw) // 2
            ty = (header_h - 28) // 2
            draw.text((tx, ty), text, fill=(255, 255, 255), font=font)
        except Exception:
            pass  # 폰트 없으면 텍스트 생략

        # 이미지 배치
        for i, cell in enumerate(cells):
            row = i // col_count
            col = i % col_count
            x = padding + col * (cell_w + padding)
            y = header_h + padding + row * (cell_w + padding)
            canvas.paste(cell, (x, y))

        # 저장
        out_path = self.output_dir / "07_gallery.png"
        canvas.save(out_path, quality=95)
        self._log(f"   💾 저장: 07_gallery.png ({len(cells)}장 배치)")
        return out_path

    # ── 통이미지 합치기 ─────────────────────────────────
    def merge_pages_to_single(self, page_results, width=None):
        """
        생성된 상세페이지 이미지들을 하나의 긴 통이미지로 합침.

        Args:
            page_results: gen_pages()에서 반환된 파일 경로 리스트
            width: 통이미지 너비 (기본값: DETAIL_PAGE_WIDTH)

        Returns:
            Path: 합쳐진 통이미지 경로 (없으면 None)
        """
        self._log("\n🖼️ STEP 4: 통이미지 합치기...")

        target_w = width or DETAIL_PAGE_WIDTH

        # 유효한 이미지만 필터링
        valid_paths = [p for p in page_results if p and Path(p).exists()]
        if not valid_paths:
            self._log("   ❌ 합칠 이미지가 없습니다.")
            return None

        self._log(f"   📸 {len(valid_paths)}장을 하나로 합칩니다 (너비: {target_w}px)")

        # 이미지 로드 & 너비 통일
        imgs = []
        for p in valid_paths:
            try:
                img = Image.open(p).convert("RGB")
                # 너비를 target_w로 리사이즈 (비율 유지)
                if img.width != target_w:
                    ratio = target_w / img.width
                    new_h = int(img.height * ratio)
                    img = img.resize((target_w, new_h), Image.LANCZOS)
                imgs.append(img)
            except Exception as e:
                self._log(f"   ⚠️ {Path(p).name} 로드 실패: {e}")

        if not imgs:
            self._log("   ❌ 유효한 이미지가 없습니다.")
            return None

        # 전체 높이 계산 & 합치기
        total_h = sum(img.height for img in imgs)
        merged = Image.new("RGB", (target_w, total_h), (255, 255, 255))

        y_offset = 0
        for img in imgs:
            merged.paste(img, (0, y_offset))
            y_offset += img.height

        # 저장
        out_path = self.output_dir / "00_상세페이지_통이미지.png"
        merged.save(out_path, quality=95)

        # 파일 크기 표시
        size_mb = out_path.stat().st_size / (1024 * 1024)
        self._log(f"   ✅ 통이미지 저장 완료: {out_path.name} ({target_w}x{total_h}px, {size_mb:.1f}MB)")

        # JPEG 버전도 생성 (용량 절약)
        if size_mb > 5:
            jpg_path = self.output_dir / "00_상세페이지_통이미지.jpg"
            merged.save(jpg_path, "JPEG", quality=90, optimize=True)
            jpg_mb = jpg_path.stat().st_size / (1024 * 1024)
            self._log(f"   ✅ JPEG 버전도 저장: {jpg_path.name} ({jpg_mb:.1f}MB)")

        return out_path

    # ── 전체 실행 (단일 제품) ────────────────────────────
    def run_single(self, image_paths, product_name="", output_dir="", existing_info=None):
        """
        단일 제품의 상세페이지를 생성합니다.

        Args:
            image_paths: 이미지 파일 경로 리스트
            product_name: 제품명
            output_dir: 출력 폴더 경로
            existing_info: 기존 제품 분석 정보 (step1에서 가져온 것)

        Returns:
            dict: 생성 결과 정보
        """
        tag = "🟢무료" if self.model["free"] else "🔴유료"
        self._log(f"\n{'='*60}")
        self._log(f"🛒 상세페이지 생성기 v2.0 — {self.model['name']} ({tag})")
        self._log(f"{'='*60}")
        self._log(f"   해상도: {RESOLUTION} | 이미지: {len(image_paths)}장")

        # 이미지 로드
        images = []
        for p in image_paths:
            try:
                img = Image.open(p)
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
                img = img.convert("RGB")
                if max(img.size) > 2048:
                    r = 2048 / max(img.size)
                    img = img.resize((int(img.size[0] * r), int(img.size[1] * r)), Image.LANCZOS)
                images.append(img)
            except Exception as e:
                self._log(f"   ⚠️ {Path(p).name} 로드 실패: {e}")

        if not images:
            self._log("❌ 유효한 이미지가 없습니다.")
            return {"success": False, "error": "이미지 없음"}

        # 출력 폴더 설정
        if not output_dir:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            s = product_name.replace(" ", "_")[:20] if product_name else "product"
            output_dir = f"output_{s}_{ts}"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 기존 정보 저장 (gen_pages에서 활용)
        self._existing_info = existing_info or {}

        # STEP 0: 제품 분석
        info = self.analyze_product(images, product_name, existing_info)

        # 분석 결과 저장
        info_path = self.output_dir / "product_info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        # STEP 1: 누끼컷 (1장만)
        nk = self.gen_nukki_single(images)
        nk_img = Image.open(nk) if nk else None
        time.sleep(WAIT_SEC)

        # STEP 2: 상세페이지 6장 (AI 생성)
        results = self.gen_pages(images, nk_img)
        success = sum(1 for r in results if r)

        # STEP 3: 갤러리 페이지 (Pillow, AI 미사용)
        gallery = self.gen_gallery_page(image_paths)
        if gallery:
            results.append(gallery)
            success += 1

        # STEP 4: 통이미지 합치기
        merged_path = self.merge_pages_to_single(results)

        # 결과 요약
        self._log(f"\n{'='*60}")
        self._log(f"✅ 상세페이지 생성 완료!")
        self._log(f"{'='*60}")
        self._log(f"   📌 모델: {self.model['name']} ({tag})")
        self._log(f"   📦 제품: {info.get('productName', '?')}")
        self._log(f"   🎯 누끼컷: {'O' if nk else 'X'}")
        self._log(f"   📄 상세페이지: {success}장 (AI {success - (1 if gallery else 0)} + 갤러리 {1 if gallery else 0})")
        self._log(f"   🖼️ 통이미지: {'O' if merged_path else 'X'}")

        if self.model["free"]:
            self._log(f"   💰 비용: 무료! ({self.generated_count}장)")
        else:
            c = self.generated_count * self.model["cost_per_img"]
            self._log(f"   💰 비용: ${c:.2f} (≈{int(c * 1350):,}원) — {self.generated_count}장")

        self._log(f"   📁 위치: {self.output_dir.absolute()}")

        return {
            "success": True,
            "product_name": info.get("productName", product_name),
            "output_dir": str(self.output_dir.absolute()),
            "nukki_count": 1 if nk else 0,
            "has_lifestyle": False,
            "page_count": success,
            "merged_image": str(merged_path) if merged_path else None,
            "total_images": self.generated_count,
            "cost_usd": 0 if self.model["free"] else self.generated_count * self.model["cost_per_img"],
            "files": sorted(str(f) for f in self.output_dir.glob("*.png")),
        }


# ═══════════════════════════════════════════════════════════
# 메인 실행 함수 (webapp.py / main.py에서 호출)
# ═══════════════════════════════════════════════════════════
def run(products, base_folder, model_no=1, api_key=None, progress_callback=None):
    """
    전체 제품의 상세페이지를 생성합니다.

    Args:
        products: {folder_name: {info: {...}, files: [...], folder_path: "..."}}
        base_folder: 기본 폴더 경로
        model_no: 모델 번호 (1~4)
        api_key: Gemini API 키 (없으면 config에서)
        progress_callback: fn(message, progress_pct)

    Returns:
        list: 생성된 결과 리스트
    """
    print("=" * 60)
    print("  STEP 4: 상세페이지 AI 이미지 자동 생성")
    print("=" * 60)

    model = get_model_by_no(model_no)
    tag = "🟢무료" if model["free"] else "🔴유료"
    print(f"\n   📌 모델: {model['name']} ({tag})")
    print(f"   💰 가격: {model['price']}")

    output_base = os.path.join(base_folder, "상세페이지")
    os.makedirs(output_base, exist_ok=True)

    # 생성기 인스턴스
    def default_progress(msg, pct=None):
        if progress_callback:
            progress_callback(msg, pct)
        print(msg)

    generator = DetailPageGenerator(
        api_key=api_key,
        model=model,
        progress_callback=default_progress,
    )

    generated = []
    total = len(products)

    for idx, (name, data) in enumerate(sorted(products.items()), 1):
        info = data.get("info", {})
        files = data.get("files", [])
        folder_path = data.get("folder_path", "")
        pname = info.get("product_name", name)

        # 저장된 경로가 실제로 없으면 folder_path에서 직접 스캔
        _img_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        valid_files = [f for f in files if os.path.exists(f)]
        if not valid_files and folder_path and os.path.isdir(folder_path):
            valid_files = [
                os.path.join(folder_path, f)
                for f in sorted(os.listdir(folder_path))
                if os.path.splitext(f)[1].lower() in _img_exts
            ]
            if valid_files:
                default_progress(f"   📂 경로 복구: {folder_path} ({len(valid_files)}장)")
        files = valid_files or files

        print(f"\n{'─'*60}")
        print(f"   [{idx}/{total}] {pname}")
        print(f"{'─'*60}")

        # 출력 폴더
        safe_name = pname.replace("/", "_").replace("\\", "_")[:30]
        product_dir = os.path.join(output_base, f"{idx:02d}_{safe_name}")

        # 실행
        result = generator.run_single(
            image_paths=files,
            product_name=pname,
            output_dir=product_dir,
            existing_info=info,
        )

        generated.append(result)

        if progress_callback:
            pct = int(idx / total * 100)
            progress_callback(f"[{idx}/{total}] {pname} 완료", pct)

    # 전체 요약
    success_count = sum(1 for g in generated if g.get("success"))
    total_pages = sum(g.get("page_count", 0) for g in generated)
    total_cost = sum(g.get("cost_usd", 0) for g in generated)

    print(f"\n{'='*60}")
    print(f"  ✅ 전체 상세페이지 생성 완료")
    print(f"{'='*60}")
    merged_count = sum(1 for g in generated if g.get("merged_image"))
    print(f"   📦 제품: {success_count}/{total}개 성공")
    print(f"   📄 상세페이지: 총 {total_pages}장 (제품당 6~7장)")
    print(f"   🖼️ 통이미지: {merged_count}/{total}개 생성 (한장 등록용)")
    if total_cost > 0:
        print(f"   💰 총 비용: ${total_cost:.2f} (≈{int(total_cost * 1350):,}원)")
    else:
        print(f"   💰 비용: 무료!")
    print(f"   📁 위치: {output_base}/")

    return generated


# ═══════════════════════════════════════════════════════════
# 후킹 이미지 단독 생성 (테스트용)
# ═══════════════════════════════════════════════════════════
def run_hooking_test(product_key, products, base_folder,
                     model_no=1, api_key=None, progress_callback=None):
    """
    후킹 이미지(01_hooking.png) 1장만 빠르게 생성.
    전체 상세페이지 없이 최상단 이미지만 테스트할 때 사용.

    Returns:
        dict: {"success": bool, "hooking_path": str, "product_name": str}
    """
    def _log(msg, pct=None):
        if progress_callback:
            progress_callback(msg, pct)
        print(msg)

    # 제품 데이터 가져오기
    data = products.get(product_key)
    if not data:
        # key 매칭 실패 시 제품명으로도 검색
        for k, v in products.items():
            if v.get("info", {}).get("product_name", "") == product_key:
                data = v
                break
    if not data:
        _log(f"❌ 제품을 찾을 수 없습니다: {product_key}")
        return {"success": False, "error": "제품 없음"}

    info = data.get("info", {})
    files = data.get("files", [])
    folder_path = data.get("folder_path", "")
    pname = info.get("product_name", product_key)

    # 파일 경로 복구
    _img_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    valid_files = [f for f in files if os.path.exists(f)]
    if not valid_files and folder_path and os.path.isdir(folder_path):
        valid_files = [
            os.path.join(folder_path, f)
            for f in sorted(os.listdir(folder_path))
            if os.path.splitext(f)[1].lower() in _img_exts
        ]

    if not valid_files:
        _log(f"❌ 이미지를 찾을 수 없습니다: {pname}")
        return {"success": False, "error": "이미지 없음"}

    model = get_model_by_no(model_no)
    cfg_key = api_key or GEMINI_API_KEY
    if not cfg_key:
        return {"success": False, "error": "API 키 없음"}

    _log(f"\n🎯 후킹 이미지 테스트 — {pname}", 10)
    _log(f"   모델: {model['name']} | 이미지: {len(valid_files)}장")

    generator = DetailPageGenerator(
        api_key=cfg_key,
        model=model,
        progress_callback=_log,
    )

    # 이미지 로드
    images = []
    for p in valid_files:
        try:
            img = Image.open(p)
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            img = img.convert("RGB")
            if max(img.size) > 2048:
                r = 2048 / max(img.size)
                img = img.resize((int(img.size[0]*r), int(img.size[1]*r)), Image.LANCZOS)
            images.append(img)
        except Exception as e:
            _log(f"   ⚠️ {Path(p).name} 로드 실패: {e}")

    if not images:
        return {"success": False, "error": "유효한 이미지 없음"}

    # 출력 폴더: 상세페이지/후킹테스트/제품명/
    output_base = os.path.join(base_folder, "상세페이지", "후킹테스트")
    safe_name = pname.replace("/", "_").replace("\\", "_")[:30]
    ts = datetime.now().strftime("%H%M%S")
    output_dir = Path(os.path.join(output_base, f"{safe_name}_{ts}"))
    output_dir.mkdir(parents=True, exist_ok=True)
    generator.output_dir = output_dir

    # 제품 분석
    _log("   🔍 제품 분석 중...", 20)
    generator._existing_info = info
    product_info = generator.analyze_product(images, pname, info)
    generator.product_info = product_info

    # 누끼컷
    _log("   ✂️ 누끼컷 생성 중...", 40)
    nk_img = generator.gen_nukki_single(images)

    # 후킹 이미지만 생성
    _log("   🎨 후킹 이미지 생성 중...", 60)

    # gen_pages와 동일한 변수 준비
    n = product_info.get("productName", pname)
    b = product_info.get("brand", info.get("brand", ""))
    h = product_info.get("hookingMents", ["한정수량 특가!"] * 5)
    pp_list = product_info.get("painPoints", [])
    ft_list = product_info.get("features", [{"title":"", "mainCopy":"", "subCopy":""}]*3)
    ds = product_info.get("description", n)
    price = product_info.get("price", info.get("price_tag", ""))
    target = product_info.get("targetCustomer", "")
    category = product_info.get("category", info.get("category", ""))
    pain0 = pp_list[0] if pp_list else ""
    ft0 = ft_list[0]["mainCopy"] if ft_list else ""
    ft1 = ft_list[1]["mainCopy"] if len(ft_list) > 1 else ""

    base_img = nk_img if nk_img and not generator.is_text_only else images[0]

    hooking_prompt = f"""쿠팡/네이버 상세페이지 최상단 후킹 이미지. 세로 비율 3:4.
소비자가 스크롤을 멈추고 "이게 내게 필요한 제품이다"라고 느끼게 만드는 이미지.

[제품 정보]
- 브랜드: {b}
- 제품명: {n}
- 카테고리: {category}
- 타겟 고객: {target}
- 제품 핵심 설명: {ds}
- 주요 기능: {ft0}{f" / {ft1}" if ft1 else ""}
- 고객 고민 해결: {pain0}
{f"- 가격: {price}" if price else ""}

[레이아웃 — 반드시 준수]
배경: 짙은 다크네이비~블랙 그라데이션. 프리미엄하고 임팩트 있게.

상단 40%: 다음 두 줄 텍스트를 화면 꽉 차게 크고 굵게 표현
  1줄: "{b} {n}" — 이게 어떤 제품인지 핵심을 담은 카피 (한국어, 흰색 굵은 고딕)
  2줄: "{h[0]}" — 노란색 하이라이트 박스 안에 강조 텍스트

중앙~하단 55%: 제품 원본 이미지를 크고 선명하게 배치. 프리미엄 조명 효과.

하단 5%: "{b}" 브랜드명 작게.
{f'가격 강조: "{price}" 빨간색으로 눈에 띄게' if price else ""}

[주의사항]
- {b} 제품 라벨/로고/텍스트 절대 변경·합성 금지. 있는 그대로 보여줄 것.
- 상단 텍스트가 "이 제품이 무엇인지, 왜 나에게 필요한지" 명확히 전달해야 함.
- 범용적인 광고 문구("최고의 선택" 등) 사용 금지. 이 제품만의 특성을 담을 것."""

    contents = [hooking_prompt, base_img] if base_img else [hooking_prompt]
    hooking_path = generator._gen_image(contents, DETAIL_RATIO, "01_hooking.png")

    _log(f"   ✅ 후킹 이미지 완료!", 100)

    return {
        "success": bool(hooking_path and Path(hooking_path).exists()),
        "hooking_path": str(hooking_path) if hooking_path else "",
        "product_name": pname,
        "output_dir": str(output_dir),
    }


# ═══════════════════════════════════════════════════════════
# CLI 직접 실행
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="🛒 상세페이지 AI 자동 생성기 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
═══ 모델 선택 ═══
  --model 1  🟢무료  나노바나나        (기본, 하루 500장)
  --model 2  🔴유료  나노바나나2  ⭐추천 (~60원/장)
  --model 3  🔴유료  나노바나나 Pro     (~180원/장)
  --model 4  🔴유료  Imagen 4 Fast     (~27원/장, 편집불가)

═══ 예시 ═══
  python step4_detail.py --images ./photos
  python step4_detail.py --images ./photos --model 2
  python step4_detail.py --images ./photos --name "올리브오일" --model 2
""",
    )
    parser.add_argument("--images", "-i", nargs="+", required=True, help="이미지 파일/폴더")
    parser.add_argument("--name", "-n", default="", help="제품명")
    parser.add_argument("--output", "-o", default="", help="출력 폴더")
    parser.add_argument("--key", "-k", default="", help="Gemini API 키")
    parser.add_argument("--model", "-m", type=int, default=1, choices=[1, 2, 3, 4], help="모델 번호")
    parser.add_argument("--resolution", "-r", default="1K", choices=["1K", "2K", "4K"], help="해상도")

    args = parser.parse_args()

    # 해상도 설정 (모듈 레벨 변수 업데이트)
    import step4_detail as _self
    _self.RESOLUTION = args.resolution

    model = get_model_by_no(args.model)

    # 이미지 경로 수집
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    paths = []
    for s in args.images:
        p = Path(s)
        if p.is_dir():
            paths.extend(str(f) for f in sorted(p.iterdir()) if f.suffix.lower() in exts)
        elif p.is_file() and p.suffix.lower() in exts:
            paths.append(str(p))

    if not paths:
        print("❌ 이미지 파일을 찾을 수 없습니다.")
        sys.exit(1)

    gen = DetailPageGenerator(api_key=args.key or None, model=model)
    result = gen.run_single(paths, args.name, args.output)

    if result["success"]:
        print(f"\n💡 팁: 텍스트가 깨진 이미지는 캔바에서 수정 후 업로드하세요!")
    else:
        print(f"\n❌ 생성 실패: {result.get('error', '알 수 없는 오류')}")
