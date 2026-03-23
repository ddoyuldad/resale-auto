"""
STEP 5 — 쿠팡 자동 등록 모듈

쿠팡 OPEN API 공식 스펙 기반 (2026.03 기준)
- Endpoint: POST /v2/providers/seller_api/apis/api/v1/marketplace/seller-products
- 인증: HMAC-SHA256 (CEA 방식)
- 등록 전 미리보기 모드 → JSON 검토 후 실제 등록

📌 사전 준비:
   1. 쿠팡 Wing (wing.coupang.com) 판매자 등록
   2. developers.coupangcorp.com 에서 OPEN API 키 발급
   3. config.py에 키 입력:
      COUPANG_ACCESS_KEY = "발급받은 Access Key"
      COUPANG_SECRET_KEY = "발급받은 Secret Key"
      COUPANG_VENDOR_ID  = "업체코드 (Wing 로그인 후 확인)"
"""
import os, json, time, hmac, hashlib
from datetime import datetime
from config import COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY, COUPANG_VENDOR_ID

COUPANG_API_BASE = "https://api-gateway.coupang.com"
PRODUCT_API_PATH = "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products"

# ─── 기본 배송/반품 설정 (config에서 가져오거나 여기서 수정) ──────
# ⚠️ 실제 사용 전에 반드시 본인 정보로 수정하세요!
DEFAULT_DELIVERY = {
    "deliveryMethod": "SEQUENCIAL",       # 일반배송(순차배송)
    "deliveryCompanyCode": "KDEXP",       # 택배사: 경동택배 (한진:HANJIN, CJ:CJGLS, 우체국:EPOST)
    "deliveryChargeType": "FREE",         # 무료배송
    "deliveryCharge": 0,                  # 기본배송비 (유료배송 시 금액 입력)
    "freeShipOverAmount": 0,              # 조건부 무료배송 금액 (무료배송이면 0)
    "deliveryChargeOnReturn": 2500,       # 초도반품배송비 (편도)
    "remoteAreaDeliverable": "N",         # 도서산간 배송 여부
    "unionDeliveryType": "UNION_DELIVERY", # 묶음배송 가능
}

DEFAULT_RETURN = {
    "returnCenterCode": "NO_RETURN_CENTERCODE",  # 센터코드 없이 직접 반품지 정보 사용
    "returnChargeName": "제이피컴퍼니 반품지",
    "companyContactNumber": "010-2843-3051",
    "returnZipCode": "12925",
    "returnAddress": "경기도 하남시 미사강변한강로 165",
    "returnAddressDetail": "aa동 9층 905호",
    "returnCharge": 2500,                 # 반품배송비 (편도)
}


# ─── HMAC-SHA256 인증 헤더 생성 ───────────────────────────────
def generate_hmac(method, url_path, datetime_str):
    """쿠팡 CEA 방식 HMAC 서명 생성"""
    message = datetime_str + method + url_path
    signature = hmac.new(
        COUPANG_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={COUPANG_ACCESS_KEY}, "
        f"signed-date={datetime_str}, signature={signature}"
    )


def get_headers(method, url_path):
    """API 요청용 헤더 생성"""
    dt = datetime.utcnow().strftime("%y%m%dT%H%M%SZ")
    return {
        "Content-Type": "application/json;charset=UTF-8",
        "Authorization": generate_hmac(method, url_path, dt),
        "X-Requested-By": COUPANG_ACCESS_KEY,
    }


# ─── 카테고리 조회 ──────────────────────────────────────────
def search_category(query):
    """쿠팡 카테고리 검색 (displayCategoryCode 확인용)"""
    import urllib.request, urllib.parse
    path = (
        "/v2/providers/marketplace_openapi/apis/api/v1/marketplace/"
        f"meta/category-related-metas/search?searchQuery={urllib.parse.quote(query)}"
    )
    url = COUPANG_API_BASE + path
    headers = get_headers("GET", path)

    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"   ⚠️  카테고리 검색 오류: {e}")
        return None


# ─── 상품 등록 데이터 생성 (공식 스펙 기반) ────────────────────
def build_product_data(product_info, images=None, naver_price=None):
    """
    쿠팡 상품 생성 API 스펙에 맞는 JSON 데이터 생성

    공식 문서: https://developers.coupangcorp.com/hc/ko/articles/360033877853
    """
    product_name = product_info.get("product_name", "상품명 미입력")
    brand = product_info.get("brand", "")
    category = product_info.get("category", "")
    spec = product_info.get("spec", "")
    price_tag = product_info.get("price_tag", "")

    # 판매가 결정: 네이버 최저가 참고 또는 이미지에서 읽은 가격
    sale_price = 0
    if naver_price and naver_price > 0:
        sale_price = naver_price
    elif price_tag:
        # "2,900원" → 2900 변환
        try:
            sale_price = int(price_tag.replace(",", "").replace("원", "").strip())
        except:
            pass

    original_price = int(sale_price * 1.2) if sale_price > 0 else 0  # 정가 = 판매가 × 1.2

    # 판매기간
    now = datetime.now()
    sale_start = now.strftime("%Y-%m-%dT00:00:00")
    sale_end = "2099-01-01T23:59:59"

    # 검색 태그 생성
    search_tags = []
    if brand:
        search_tags.append(brand)
    for word in product_name.split():
        if len(word) >= 2 and word not in search_tags:
            search_tags.append(word)
    search_tags = search_tags[:20]  # 최대 20개

    # ── 메인 데이터 구조 ──
    data = {
        # 카테고리 (미입력 시 쿠팡이 자동매칭)
        "displayCategoryCode": 0,

        # 상품 기본정보
        "sellerProductName": product_name[:100],
        "vendorId": COUPANG_VENDOR_ID,
        "saleStartedAt": sale_start,
        "saleEndedAt": sale_end,
        "displayProductName": f"{brand} {product_name}"[:100] if brand else product_name[:100],
        "brand": brand.replace(" ", ""),  # 띄어쓰기/특수문자 없이
        "generalProductName": product_name[:100],
        "productGroup": category if category else "",
        "manufacture": brand if brand else "",

        # 배송 정보
        **DEFAULT_DELIVERY,

        # 반품 정보
        **DEFAULT_RETURN,

        # 출고지
        "outboundShippingPlaceCode": 0,   # ← 출고지 조회 API로 확인 후 입력

        # 판매자 정보
        "vendorUserId": "",               # ← Wing 로그인 ID 입력

        # ⚠️ False = 저장만 (판매요청 안 함), True = 저장 + 자동 판매승인 요청
        "requested": False,

        # 상품 옵션 (아이템)
        "items": [
            {
                "itemName": f"{product_name}_1개",
                "originalPrice": original_price,
                "salePrice": sale_price,
                "maximumBuyCount": 99999,
                "maximumBuyForPerson": 0,          # 0 = 제한 없음
                "maximumBuyForPersonPeriod": 1,
                "outboundShippingTimeDay": 2,       # D+2 출고
                "unitCount": 1,
                "adultOnly": "EVERYONE",
                "taxType": "TAX",
                "parallelImported": "NOT_PARALLEL_IMPORTED",
                "overseasPurchased": "NOT_OVERSEAS_PURCHASED",
                "pccNeeded": False,
                "externalVendorSku": "",
                "barcode": "",
                "emptyBarcode": True,
                "emptyBarcodeReason": "자체상품_바코드없음",
                "modelNo": "",

                # 인증정보
                "certifications": [
                    {
                        "certificationType": "NOT_REQUIRED",
                        "certificationCode": ""
                    }
                ],

                # 검색태그
                "searchTags": search_tags,

                # 이미지 (vendorPath 또는 cdnPath 필수)
                "images": [],

                # 상품고시정보
                "notices": [
                    {"noticeCategoryName": "기타", "noticeCategoryDetailName": "품명 및 모델명", "content": product_name},
                    {"noticeCategoryName": "기타", "noticeCategoryDetailName": "제조자(수입자)", "content": brand if brand else "상세페이지 참조"},
                    {"noticeCategoryName": "기타", "noticeCategoryDetailName": "제조국", "content": "상세페이지 참조"},
                    {"noticeCategoryName": "기타", "noticeCategoryDetailName": "소비자상담 관련 전화번호", "content": "상세페이지 참조"},
                ],

                # 구매옵션 (카테고리별 필수옵션은 카테고리 메타 API로 확인)
                "attributes": [
                    {
                        "attributeTypeName": "수량",
                        "attributeValueName": "1개"
                    }
                ],

                # 상세페이지 컨텐츠
                "contents": [],

                "offerCondition": "NEW",
                "offerDescription": "",
            }
        ],

        # 구비서류
        "requiredDocuments": [],
        "extraInfoMessage": "",

        # 번들 (단일상품)
        "bundleInfo": {
            "bundleType": "SINGLE"
        },
    }

    # ── 이미지 추가 ──
    if images:
        for i, img_path in enumerate(images[:10]):  # 대표1 + 기타9 = 최대 10장
            data["items"][0]["images"].append({
                "imageOrder": i,
                "imageType": "REPRESENTATION" if i == 0 else "DETAIL",
                "vendorPath": img_path,  # http:// URL 또는 쿠팡 CDN 경로
                "cdnPath": "",
            })

    # ── 상세페이지 컨텐츠 ──
    # Step 4에서 생성한 HTML 상세페이지를 여기에 연결 가능
    if spec:
        data["items"][0]["contents"].append({
            "contentsType": "TEXT",
            "contentDetails": [
                {
                    "content": f"<p>{spec}</p>",
                    "detailType": "TEXT"
                }
            ]
        })

    return data


# ─── 상품 등록 API 호출 ─────────────────────────────────────
def register_product(product_data):
    """쿠팡에 상품 등록 (POST)"""
    import urllib.request

    url = COUPANG_API_BASE + PRODUCT_API_PATH
    headers = get_headers("POST", PRODUCT_API_PATH)

    body = json.dumps(product_data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))

        if result.get("code") == "SUCCESS" or (result.get("data") and result["data"].get("code") == "SUCCESS"):
            seller_product_id = result.get("data", {}).get("data", result.get("data"))
            print(f"      ✅ 등록 성공! sellerProductId: {seller_product_id}")
        elif result.get("code") == "ERROR":
            print(f"      ❌ 등록 실패: {result.get('message', '')}")
            if result.get("errorItems"):
                for err in result["errorItems"]:
                    print(f"         - [{err.get('itemName')}] {err.get('itemAttributes', [])}")
        return result

    except Exception as e:
        print(f"   ⚠️  등록 API 오류: {e}")
        return None


# ─── 메인 실행 ─────────────────────────────────────────────
def run(products, naver_results=None):
    print("=" * 60)
    print("  STEP 5: 쿠팡 상품 등록")
    print("=" * 60)

    # API 키 미설정 시 가이드 표시
    if not COUPANG_ACCESS_KEY or not COUPANG_SECRET_KEY:
        print("\n" + "─" * 50)
        print("  📋 쿠팡 자동 등록 — 설정 안내")
        print("─" * 50)
        print("""
  ✅ 쿠팡 OPEN API로 자동 등록이 가능합니다!

  📌 사전 준비 (한번만 하면 됩니다):

  1단계. 쿠팡 Wing 판매자 등록
     → https://wing.coupang.com
     → 사업자등록증, 통장사본 필요

  2단계. OPEN API 키 발급
     → developers.coupangcorp.com 에서 로그인
     → 또는 Wing → 기타 서비스 → 쿠팡 API 링크
     → Access Key, Secret Key 발급

  3단계. config.py에 입력
     COUPANG_ACCESS_KEY = "발급받은 Access Key"
     COUPANG_SECRET_KEY = "발급받은 Secret Key"
     COUPANG_VENDOR_ID  = "업체코드 (Wing 판매자정보에서 확인)"

  4단계. 반품지/출고지 설정
     → Wing에서 반품지, 출고지를 먼저 등록
     → step5_coupang.py 상단의 DEFAULT_RETURN에 정보 입력

  5단계. 다시 이 프로그램 실행 → Step 5 선택

  ⚠️ 주의사항:
  - 처음에는 requested=False (저장만) 로 테스트 권장
  - JSON 미리보기 파일을 꼭 검토 후 실제 등록 진행
  - 카테고리코드는 미입력 시 쿠팡이 자동매칭 가능
  - 이미지는 http:// URL이 필요 (로컬 파일은 먼저 업로드)
""")
        return

    # Vendor ID 체크
    if not COUPANG_VENDOR_ID:
        print("\n  ⚠️  COUPANG_VENDOR_ID가 비어있습니다.")
        print("     Wing 로그인 → 판매자정보에서 업체코드를 확인 후 config.py에 입력해 주세요.")
        return

    # 네이버 최저가 매핑
    price_map = {}
    if naver_results:
        for r in naver_results:
            name = r.get("product_name", "")
            price = r.get("price", 0)
            if name and price > 0:
                price_map[name] = price

    print(f"\n📦 {len(products)}개 제품 쿠팡 등록 데이터 생성 중...\n")

    # 저장 디렉토리
    output_dir = os.path.join(os.path.dirname(list(products.values())[0].get("folder_path", ".")), "쿠팡등록데이터")
    os.makedirs(output_dir, exist_ok=True)

    results = []
    for idx, (name, data) in enumerate(sorted(products.items()), 1):
        info = data["info"]
        pname = info.get("product_name", name)
        print(f"   [{idx}/{len(products)}] {pname}")

        # 네이버 가격 참조
        naver_price = price_map.get(pname, 0)

        # 등록 데이터 생성
        product_data = build_product_data(info, naver_price=naver_price)

        # JSON 미리보기 저장
        safe_name = pname.replace("/", "_").replace("\\", "_")[:30]
        preview_path = os.path.join(output_dir, f"{idx:02d}_{safe_name}.json")
        with open(preview_path, "w", encoding="utf-8") as f:
            json.dump(product_data, f, ensure_ascii=False, indent=2)

        print(f"      💾 미리보기 저장: {preview_path}")

        if sale_price := product_data["items"][0]["salePrice"]:
            print(f"      💰 판매가: {sale_price:,}원")
        else:
            print(f"      ⚠️  판매가 미설정 (JSON에서 직접 입력 필요)")

        results.append({
            "name": pname,
            "json_path": preview_path,
            "data": product_data,
        })

    # 실제 등록 여부 확인
    print(f"\n{'─' * 50}")
    print(f"  📋 {len(results)}건 JSON 미리보기 생성 완료")
    print(f"  📂 저장 위치: {output_dir}")
    print(f"{'─' * 50}")
    print()
    print("  ⚠️  현재는 '미리보기 모드'입니다.")
    print("     JSON 파일을 검토한 후 실제 등록을 진행하세요.")
    print()
    print("  📝 등록 전 체크리스트:")
    print("     □ displayCategoryCode (카테고리코드) 확인")
    print("     □ salePrice (판매가) 확인")
    print("     □ images (이미지 URL) 추가")
    print("     □ returnCenterCode (반품지 센터코드) 입력")
    print("     □ outboundShippingPlaceCode (출고지 코드) 입력")
    print("     □ vendorUserId (Wing 로그인 ID) 입력")
    print("     □ notices (상품고시정보) 카테고리에 맞게 수정")
    print()

    # 등록 실행 옵션
    do_register = input("  실제 쿠팡에 등록하시겠습니까? (y/n): ").strip().lower()
    if do_register == 'y':
        confirm = input("  ⚠️  정말 등록합니까? 되돌릴 수 없습니다. (yes 입력): ").strip()
        if confirm == 'yes':
            print("\n🚀 쿠팡 등록 시작...\n")
            for r in results:
                print(f"   📦 {r['name']}...")
                result = register_product(r["data"])
                if result:
                    r["api_result"] = result
                time.sleep(1)  # API 호출 간격
            print(f"\n✅ 등록 완료! Wing에서 상품 상태를 확인하세요.")
        else:
            print("\n  → 등록을 취소했습니다.")
    else:
        print("\n  → JSON 파일을 검토 후 다시 실행해 주세요.")

    return results


if __name__ == "__main__":
    print("이 모듈은 main.py를 통해 실행해 주세요.")
