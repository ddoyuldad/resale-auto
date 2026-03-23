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
import os, sys, json, time, glob
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
except ImportError:
    GEMINI_API_KEY = ""
    DETAIL_PAGE_WIDTH = 860

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

        prompt = f"""너는 쿠팡/네이버 스마트스토어 전문 상세페이지 기획자야.
첨부한 제품 사진들을 분석하고 상세페이지 기획을 해줘.
{"상품명: " + product_name if product_name else "상품명을 사진에서 읽어서 파악해줘."}
{"브랜드: " + brand if brand else ""}
{"카테고리: " + category if category else ""}
{"제품특징: " + feature if feature else ""}
{"셀링포인트: " + selling_point if selling_point else ""}

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

    # ── 상세페이지 12장 생성 ─────────────────────────────
    def gen_pages(self, images, nukki=None, life=None):
        self._log("\n📄 STEP 3: 상세페이지 12장 생성 중...")
        info = self.product_info
        n = info.get("productName", "제품")
        b = info.get("brand", "")
        bg = get_background_for_category(info.get("category", "기타"))
        h = info.get("hookingMents", ["이 가격에 이 퀄리티?"] * 5)
        pp = info.get("painPoints", ["고민1", "고민2", "고민3"])
        ft = info.get("features", [{"title": "특징", "mainCopy": "품질", "subCopy": "설명"}] * 3)
        us = info.get("usageTips", ["활용1", "활용2", "활용3", "활용4"])
        sp = info.get("specs", "스펙")
        pc = info.get("priceCompare", "초특가")
        ct = info.get("ctaCopy", "구매 🛒")
        ds = info.get("description", n)

        base = nukki or images[0]
        lf = life or base
        ce = not self.is_text_only  # can_edit: 이미지 편집 가능 여부

        # 12장 페이지 정의: (파일명, 참조이미지, 프롬프트)
        pages = [
            ("01_hooking.png", lf if ce else None,
             f"""쿠팡 최상단 후킹 썸네일. {n} 제품. 배경: {bg}, 약간 어둡게.
제품 중앙~하단 크게. 상단 굵은고딕 "{h[0]}" 흰색+검정그림자.
하단 "{h[1] if len(h)>1 else ''}" 노란하이라이트. 긴급+프리미엄. {b} 라벨 유지."""),

            ("02_painpoint.png", None,
             f"""고객고민 공감 이미지. 배경: 연회색 그라데이션.
상단 "혹시 이런 고민 있으신가요?" 굵은고딕.
3개포인트: ❌"{pp[0]}" ❌"{pp[1] if len(pp)>1 else ''}" ❌"{pp[2] if len(pp)>2 else ''}" 아이콘+텍스트 세로나열."""),

            ("03_solution.png", lf if ce else None,
             f"""솔루션 이미지. 밝고 따뜻한톤. 상단 "그래서 준비했습니다 ✨"
중앙 {n} 크게. 하단 "{ds}". 밝고 희망적. {b} 라벨유지."""),

            ("04_feature1.png", base if ce else None,
             f"""{n} 특징1. 좌40%제품+우60%텍스트. 크림배경.
메인: "{ft[0]['mainCopy']}" 서브: "{ft[0]['subCopy']}". {b} 라벨유지."""),

            ("05_feature2.png", base if ce else None,
             f"""{n} 특징2. 우40%제품+좌60%텍스트. 민트배경.
메인: "{ft[1]['mainCopy'] if len(ft)>1 else ''}" 서브: "{ft[1]['subCopy'] if len(ft)>1 else ''}". {b} 라벨유지."""),

            ("06_feature3.png", base if ce else None,
             f"""{n} 특징3. 중앙제품+상하텍스트. 블루배경.
메인: "{ft[2]['mainCopy'] if len(ft)>2 else ''}" 서브: "{ft[2]['subCopy'] if len(ft)>2 else ''}". {b} 라벨유지."""),

            ("07_usage.png", base if ce else None,
             f"""{n} 활용법. 2x2그리드: {us[0]}/{us[1] if len(us)>1 else ''}/{us[2] if len(us)>2 else ''}/{us[3] if len(us)>3 else ''}.
각칸 라벨텍스트. 따뜻한 라이프스타일."""),

            ("08_specs.png", base if ce else None,
             f"""{n} 스펙정보. 화이트배경. 상단 "꼼꼼히 확인하세요 📋"
중앙: {sp} 인포그래픽. 하단 제품소. 신뢰감."""),

            ("09_review.png", None,
             f"""리뷰 이미지. 크림배경. 상단 "구매자 솔직후기 💬"
3개 말풍선카드: ⭐⭐⭐⭐⭐"재구매100%" ⭐⭐⭐⭐⭐"{n}최고" ⭐⭐⭐⭐⭐"가성비 강추"."""),

            ("10_price.png", base if ce else None,
             f"""{n} 가성비. 밝은배경. 상단 "이 가격, 실화입니다 💰"
"{pc}" 할인율 빨간글씨. 하단 제품. {b} 라벨유지."""),

            ("11_shipping.png", None,
             """배송안내. 블루/화이트. 상단 "안심하고 주문하세요 📦"
🚀빠른배송 🔄교환반품 💯정품보장. 아이콘+텍스트."""),

            ("12_cta.png", lf if ce else None,
             f"""{n} CTA마무리. 어두운 그라데이션. 제품 크게+금빛하이라이트.
상단 "더 이상 고민하지 마세요" 흰색. 하단 "{ct}" 노란강조. {b} 라벨유지."""),
        ]

        results = []
        for idx, (fname, img, prompt) in enumerate(pages):
            label = fname.split("_", 1)[1].replace(".png", "")
            self._log(f"\n   📸 [{idx+1}/{len(pages)}] {label}")
            contents = [prompt, img] if img else [prompt]
            results.append(self._gen_image(contents, DETAIL_RATIO, fname))
            time.sleep(WAIT_SEC)

        return results

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

        # STEP 0: 제품 분석
        info = self.analyze_product(images, product_name, existing_info)

        # 분석 결과 저장
        info_path = self.output_dir / "product_info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        # STEP 1: 누끼컷
        nk = self.gen_nukki(images)
        nk_img = Image.open(nk[0]) if nk else None
        time.sleep(WAIT_SEC)

        # STEP 2: 라이프스타일
        lf_img = None
        if nk_img:
            lp = self.gen_lifestyle(nk_img)
            if lp:
                lf_img = Image.open(lp)
        time.sleep(WAIT_SEC)

        # STEP 3: 상세페이지 12장
        results = self.gen_pages(images, nk_img, lf_img)
        success = sum(1 for r in results if r)

        # 결과 요약
        self._log(f"\n{'='*60}")
        self._log(f"✅ 상세페이지 생성 완료!")
        self._log(f"{'='*60}")
        self._log(f"   📌 모델: {self.model['name']} ({tag})")
        self._log(f"   📦 제품: {info.get('productName', '?')}")
        self._log(f"   🎯 누끼컷: {len(nk)}장 | 🌿 라이프스타일: {'O' if lf_img else 'X'}")
        self._log(f"   📄 상세페이지: {success}/12장 성공")

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
            "nukki_count": len(nk),
            "has_lifestyle": bool(lf_img),
            "page_count": success,
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
        pname = info.get("product_name", name)

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
    print(f"   📦 제품: {success_count}/{total}개 성공")
    print(f"   📄 상세페이지: 총 {total_pages}장")
    if total_cost > 0:
        print(f"   💰 총 비용: ${total_cost:.2f} (≈{int(total_cost * 1350):,}원)")
    else:
        print(f"   💰 비용: 무료!")
    print(f"   📁 위치: {output_base}/")

    return generated


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
