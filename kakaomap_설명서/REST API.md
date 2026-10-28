카카오맵

# REST API

이 문서는 REST API를 사용한 카카오맵 API 구현 방법을 안내합니다.

이 문서에 포함된 기능은 [도구] > [REST API 테스트]에서 사용해 볼 수 있습니다.

## 주소 / 좌표 변환

### 주소로 좌표 변환

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/local/search/address.${FORMAT}` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

요청한 문자열 주소의 좌표와 세부 정보를 반환합니다.

**검색어에 상세 주소 제외 권장**

검색 질의어(`query`)에 상세 주소(지번, 도로명 번호 하위의 건물명 등)는 제외하고 요청할 것을 권장합니다. 상세 주소는 입력 형태가 다양해 정확한 검색 결과를 보장하기 어렵습니다.

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 경로 변수

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| FORMAT | `Enum` | 응답 형식   - `json`: JSON 형식(기본값) - `xml`: XML 형식 | X |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| query | `String` | 검색을 원하는 질의어, 지번 주소와 도로명 주소 모두 지원 | O |
| analyze\_type | `Enum` | 검색 결과 제공 방식   - `similar`: 입력한 건물명과 일부만 매칭될 경우에도 확장된 검색 결과 제공(기본값) - `exact`: 주소의 정확한 건물명이 입력된 주소패턴일 경우에 한해, 입력한 건물명과 정확히 일치하는 검색 결과 제공   **참고**: [품질 향상을 위한 주소로 좌표 변환 API 업데이트](https://devtalk.kakao.com/t/112161) | X |
| page | `Integer` | 결과 페이지 번호(최소: `1`, 최대: `45`, 기본값: `1`) | X |
| size | `Integer` | 한 페이지로 표시할 결과 수(최소: `1`, 최대: `30`, 기본값: `10`) | X |

#### 응답

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Content-Type | 응답 데이터 타입, 아래 중 하나   - `content-type: application/json;charset=UTF-8` - `content-type: text/xml;charset=UTF-8` | O |

##### 본문

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| meta | [`Meta`](#주소로%20좌표%20변환#응답#Meta) | 조회 결과 메타 정보 |
| documents | [`Document[]`](#주소로%20좌표%20변환#응답#Document) | 주소 검색 결과 목록 |

##### Meta

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| total\_count | `Integer` | 검색어(`query`)로 검색된 결과 수 |
| pageable\_count | `Integer` | `total_count` 중 노출 가능 결과 수 |
| is\_end | `Boolean` | 현재 페이지가 마지막 페이지인지 여부, 값이 `false`인 경우 다음 요청 시 `page` 값을 증가시켜 다음 페이지 요청 가능 |

##### Document

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| address\_name | `String` | 전체 지번 주소 또는 전체 도로명 주소, 입력에 따라 결정 |
| address\_type | `Enum` | `address_name`의 종류   - `REGION`: 지명 - `ROAD`: 도로명 - `REGION_ADDR`: 지번 주소 - `ROAD_ADDR`: 도로명 주소 |
| x | `String` | X 좌표값, 좌표계가 경위도(`WGS84`)인 경우 경도(Longitude) |
| y | `String` | Y 좌표값, 좌표계가 경위도(`WGS84`)인 경우 위도(Latitude) |
| address | [`Address`](#주소로%20좌표%20변환#응답#Address) | 지번 주소 상세 정보 |
| road\_address | [`RoadAddress`](#주소로%20좌표%20변환#응답#RoadAddress) | 도로명 주소 상세 정보 |

##### Address

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| address\_name | `String` | 전체 지번 주소 |
| region\_1depth\_name | `String` | 지역 1 Depth, 시도 단위 |
| region\_2depth\_name | `String` | 지역 2 Depth, 구 단위 |
| region\_3depth\_name | `String` | 지역 3 Depth, 동 단위 |
| region\_3depth\_h\_name | `String` | 지역 3 Depth, 행정동 명칭 |
| h\_code | `String` | 행정 코드 |
| b\_code | `String` | 법정 코드 |
| mountain\_yn | `Enum` | 산(Mountain) 여부   - `Y`: 산 - `N`: 산 아님 |
| main\_address\_no | `String` | 지번 주번지 |
| sub\_address\_no | `String` | 지번 부번지, 없을 경우 빈 문자열(`""`) 반환 |
| x | `String` | X 좌표값, 좌표계가 경위도(`WGS84`)인 경우 경도(Longitude) |
| y | `String` | Y 좌표값, 좌표계가 경위도(`WGS84`)인 경우 위도(Latitude) |

\* `zip_code`: Deprecated, 우편번호(String), 6자리, [공지](https://devtalk.kakao.com/t/api-6/93000) 참고

##### RoadAddress

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| address\_name | `String` | 전체 도로명 주소 |
| region\_1depth\_name | `String` | 지역 1 Depth |
| region\_2depth\_name | `String` | 지역 2 Depth |
| region\_3depth\_name | `String` | 지역 3 Depth |
| road\_name | `String` | 도로명 |
| underground\_yn | `Enum` | 지하 여부   - `Y`: 지하 - `N`: 지상 |
| main\_building\_no | `String` | 건물 본번 |
| sub\_building\_no | `String` | 건물 부번, 없을 경우 빈 문자열(`""`) 반환 |
| building\_name | `String` | 건물 이름 |
| zone\_no | `String` | 우편번호(5자리) |
| x | `String` | X 좌표값, 좌표계가 경위도(`WGS84`)인 경우 경도(Longitude) |
| y | `String` | Y 좌표값, 좌표계가 경위도(`WGS84`)인 경우 위도(Latitude) |

#### 예제

##### 요청

```shellscript
curl -v -G "https://dapi.kakao.com/v2/local/search/address.json" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  --data-urlencode "query=전북 삼성동 100"
```

##### 응답

```json
// HTTP/1.1 200 OK
// Content-Type: application/json;charset=UTF-8
{
  "meta": {
    "total_count": 4,
    "pageable_count": 4,
    "is_end": true
  },
  "documents": [
    {
      "address_name": "전북 익산시 부송동 100",
      "y": "35.97664845766847",
      "x": "126.99597295767953",
      "address_type": "REGION_ADDR",
      "address": {
        "address_name": "전북 익산시 부송동 100",
        "region_1depth_name": "전북",
        "region_2depth_name": "익산시",
        "region_3depth_name": "부송동",
        "region_3depth_h_name": "삼성동",
        "h_code": "4514069000",
        "b_code": "4514013400",
        "mountain_yn": "N",
        "main_address_no": "100",
        "sub_address_no": "",
        "x": "126.99597295767953",
        "y": "35.97664845766847"
      },
      "road_address": {
        "address_name": "전북 익산시 망산길 11-17",
        "region_1depth_name": "전북",
        "region_2depth_name": "익산시",
        "region_3depth_name": "부송동",
        "road_name": "망산길",
        "underground_yn": "N",
        "main_building_no": "11",
        "sub_building_no": "17",
        "building_name": "",
        "zone_no": "54547",
        "y": "35.976749396987046",
        "x": "126.99599512792346"
      }
    }
    // ...
  ]
}
```

### 좌표로 행정구역정보 변환

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/local/geo/coord2regioncode.${FORMAT}` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

지정한 좌표값에 해당하는 행정동과 법정동 정보를 반환합니다.

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 경로 변수

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| FORMAT | `Enum` | 응답 형식   - `json`: JSON 형식(기본값) - `xml`: XML 형식 | X |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| x | `Double` | X 좌표값, 좌표계가 경위도(`WGS84`)인 경우 경도(Longitude) | O |
| y | `Double` | Y 좌표값, 좌표계가 경위도(`WGS84`)인 경우 위도(Latitude) | O |
| input\_coord | `Enum` | 좌표값(`x`, `y`)에 적용할 좌표계   - `WGS84`(기본값) - `WCONGNAMUL` - `CONGNAMUL` - `WTM` - `TM` | X |
| output\_coord | `Enum` | 응답에 적용할 좌표계   - `WGS84`(기본값) - `WCONGNAMUL` - `CONGNAMUL` - `WTM` - `TM` | X |

#### 응답

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Content-Type | 응답 데이터 타입, 아래 중 하나   - `content-type: application/json;charset=UTF-8` - `content-type: text/xml;charset=UTF-8` | O |

##### 본문

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| meta | [`Meta`](#좌표로%20행정구역정보%20변환#응답#Meta) | 조회 결과 메타 정보 |
| documents | [`Document[]`](#좌표로%20행정구역정보%20변환#응답#Document) | 좌표에 해당하는 행정구역 정보 목록 |

##### Meta

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| total\_count | `Integer` | 조회된 행정구역 수 |

##### Document

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| region\_type | `Enum` | 행정동과 법정동 구분   - `H`: 행정동 - `B`: 법정동 |
| address\_name | `String` | 전체 지역 명칭 |
| region\_1depth\_name | `String` | 지역 1 Depth, 시도 단위, 바다(Sea) 영역인 경우 미포함 |
| region\_2depth\_name | `String` | 지역 2 Depth, 구 단위, 바다(Sea) 영역인 경우 미포함 |
| region\_3depth\_name | `String` | 지역 3 Depth, 동 단위, 바다(Sea) 영역인 경우 미포함 |
| region\_4depth\_name | `String` | 지역 4 Depth  **중요**: `region_type`이 법정동이며 리 영역인 경우만 존재 |
| code | `String` | 행정동 또는 법정동 코드 |
| x | `Double` | X 좌표값, 좌표계가 경위도(`WGS84`)인 경우 경도(Longitude) |
| y | `Double` | Y 좌표값, 좌표계가 경위도(`WGS84`)인 경우 위도(Latitude) |

#### 예제

##### 요청

```shellscript
curl -v -G "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  -d "x=127.1086228" \
  -d "y=37.4012191"
```

##### 응답

```json
// HTTP/1.1 200 OK
// Content-Type: application/json;charset=UTF-8
{
  "meta": {
    "total_count": 2
  },
  "documents": [
    {
      "region_type": "B",
      "address_name": "경기도 성남시 분당구 삼평동",
      "region_1depth_name": "경기도",
      "region_2depth_name": "성남시 분당구",
      "region_3depth_name": "삼평동",
      "region_4depth_name": "",
      "code": "4113510900",
      "x": 127.10459896729914,
      "y": 37.40269721785548
    },
    {
      "region_type": "H",
      "address_name": "경기도 성남시 분당구 삼평동",
      "region_1depth_name": "경기도",
      "region_2depth_name": "성남시 분당구",
      "region_3depth_name": "삼평동",
      "region_4depth_name": "",
      "code": "4113565500",
      "x": 127.1163593869371,
      "y": 37.40612091848614
    }
  ]
}
```

### 좌표로 주소 변환

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/local/geo/coord2address.${FORMAT}` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

지정한 좌표값에 해당하는 지번 주소와 도로명 주소 정보를 반환합니다.

**도로명 주소 반환**

지정한 좌표에 따라 도로명 주소는 반환되지 않을 수 있습니다.

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 경로 변수

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| FORMAT | `Enum` | 응답 형식   - `json`: JSON 형식(기본값) - `xml`: XML 형식 | X |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| x | `Double` | X 좌표값, 좌표계가 경위도(`WGS84`)인 경우 경도(Longitude) | O |
| y | `Double` | Y 좌표값, 좌표계가 경위도(`WGS84`)인 경우 위도(Latitude) | O |
| input\_coord | `Enum` | 좌표값(`x`, `y`)에 적용할 좌표계   - `WGS84`(기본값) - `WCONGNAMUL` - `CONGNAMUL` - `WTM` - `TM` | X |

#### 응답

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Content-Type | 응답 데이터 타입, 아래 중 하나   - `content-type: application/json;charset=UTF-8` - `content-type: text/xml;charset=UTF-8` | O |

##### 본문

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| meta | [`Meta`](#좌표로%20주소%20변환#응답#Meta) | 조회 결과 메타 정보 |
| documents | [`Document[]`](#좌표로%20주소%20변환#응답#Document) | 좌표에 해당하는 주소 정보 목록 |

##### Meta

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| total\_count | `Integer` | 변환된 지번 주소 및 도로명 주소의 개수, `0` 또는 `1` |

##### Document

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| address | [`Address`](#좌표로%20주소%20변환#응답#Address) | 지번 주소 상세 정보 |
| road\_address | [`RoadAddress`](#좌표로%20주소%20변환#응답#RoadAddress) | 도로명 주소 상세 정보 |

##### Address

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| address\_name | `String` | 전체 지번 주소 |
| region\_1depth\_name | `String` | 지역 1 Depth, 시도 단위 |
| region\_2depth\_name | `String` | 지역 2 Depth, 구 단위 |
| region\_3depth\_name | `String` | 지역 3 Depth, 동 단위 |
| mountain\_yn | `Enum` | 산(Mountain) 여부   - `Y`: 산 - `N`: 산 아님 |
| main\_address\_no | `String` | 지번 주번지 |
| sub\_address\_no | `String` | 지번 부번지, 없을 경우 빈 문자열(`""`) 반환 |

\* `zip_code`: Deprecated, 우편번호(String), 6자리, [공지](https://devtalk.kakao.com/t/api-6/93000) 참고

##### RoadAddress

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| address\_name | `String` | 전체 도로명 주소 |
| region\_1depth\_name | `String` | 지역 1 Depth |
| region\_2depth\_name | `String` | 지역 2 Depth |
| region\_3depth\_name | `String` | 지역 3 Depth |
| road\_name | `String` | 도로명 |
| underground\_yn | `Enum` | 지하 여부   - `Y`: 지하 - `N`: 지상 |
| main\_building\_no | `String` | 건물 본번 |
| sub\_building\_no | `String` | 건물 부번, 없을 경우 빈 문자열(`""`) 반환 |
| building\_name | `String` | 건물 이름 |
| zone\_no | `String` | 우편번호(5자리) |

#### 예제

##### 요청

```shellscript
curl -v -G "https://dapi.kakao.com/v2/local/geo/coord2address.json" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  -d "x=127.423084873712" \
  -d "y=37.0789561558879" \
  -d "input_coord=WGS84"
```

##### 응답

```json
// HTTP/1.1 200 OK
// Content-Type: application/json;charset=UTF-8
{
  "meta": {
    "total_count": 1
  },
  "documents": [
    {
      "road_address": {
        "address_name": "경기도 안성시 죽산면 죽산초교길 69-4",
        "region_1depth_name": "경기",
        "region_2depth_name": "안성시",
        "region_3depth_name": "죽산면",
        "road_name": "죽산초교길",
        "underground_yn": "N",
        "main_building_no": "69",
        "sub_building_no": "4",
        "building_name": "무지개아파트",
        "zone_no": "17519"
      },
      "address": {
        "address_name": "경기 안성시 죽산면 죽산리 343-1",
        "region_1depth_name": "경기",
        "region_2depth_name": "안성시",
        "region_3depth_name": "죽산면 죽산리",
        "mountain_yn": "N",
        "main_address_no": "343",
        "sub_address_no": "1"
      }
    }
  ]
}
```

### 좌표계 변환

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/local/geo/transcoord.${FORMAT}` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

특정 좌표계의 좌표값을, 지정한 좌표계의 좌표값으로 반환합니다.

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 경로 변수

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| FORMAT | `Enum` | 응답 형식   - `json`: JSON 형식(기본값) - `xml`: XML 형식 | X |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| x | `Double` | X 좌표값, 좌표계가 경위도(`WGS84`)인 경우 경도(Longitude) | O |
| y | `Double` | Y 좌표값, 좌표계가 경위도(`WGS84`)인 경우 위도(Latitude) | O |
| input\_coord | `Enum` | 좌표값(`x`, `y`)에 적용할 좌표계   - `WGS84`(기본값) - `WCONGNAMUL` - `CONGNAMUL` - `WTM` - `TM` - `KTM` - `UTM` - `BESSEL` - `WKTM` - `WUTM` | X |
| output\_coord | `Enum` | 응답에 적용할 좌표계   - `WGS84`(기본값) - `WCONGNAMUL` - `CONGNAMUL` - `WTM` - `TM` - `KTM` - `UTM` - `BESSEL` - `WKTM` - `WUTM` | X |

#### 응답

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Content-Type | 응답 데이터 타입, 아래 중 하나   - `content-type: application/json;charset=UTF-8` - `content-type: text/xml;charset=UTF-8` | O |

##### 본문

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| meta | [`Meta`](#좌표계%20변환#응답#Meta) | 조회 결과 메타 정보 |
| documents | [`Document[]`](#좌표계%20변환#응답#Document) | 변환된 좌표 정보 목록 |

##### Meta

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| total\_count | `Integer` | 변환된 좌표 수 |

##### Document

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| x | `Double` | X 좌표값, 좌표계가 경위도(`WGS84`)인 경우 경도(Longitude) |
| y | `Double` | Y 좌표값, 좌표계가 경위도(`WGS84`)인 경우 위도(Latitude) |

#### 예제

##### 요청

```shellscript
curl -v -G "https://dapi.kakao.com/v2/local/geo/transcoord.json" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  -d "x=160710.37729270622" \
  -d "y=-4388.879299157299" \
  -d "input_coord=WTM" \
  -d "output_coord=WGS84"
```

##### 응답

```json
// HTTP/1.1 200 OK
// Content-Type: application/json;charset=UTF-8
{
  "meta": {
    "total_count": 1
  },
  "documents": [
    {
      "x": 126.57740680000002,
      "y": 33.453357700000005
    }
  ]
}
```

## 장소 검색

### 키워드로 장소 검색

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/local/search/keyword.${FORMAT}` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

요청한 키워드에 부합하는 장소 검색 결과를 지정한 정렬 기준으로 반환합니다.

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 경로 변수

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| FORMAT | `Enum` | 응답 형식   - `json`: JSON 형식(기본값) - `xml`: XML 형식 | X |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| query | `String` | 검색을 원하는 질의어 | O |
| category\_group\_code | [`Enum: CategoryGroupCode`](#Enum:%20CategoryGroupCode) | 카테고리 그룹 코드, 카테고리로 결과 필터링을 원하는 경우 사용 | X |
| x | `String` | 검색할 중심 좌표의 X값, 경도(Longitude)  **참고**: `radius`와 함께 사용해 중심 좌표와 반경 검색 가능 | X |
| y | `String` | 검색할 중심 좌표의 Y값, 위도(Latitude)  **참고**: `radius`와 함께 사용해 중심 좌표와 반경 검색 가능 | X |
| radius | `Integer` | 중심 좌표부터의 검색 반경 거리(최소: `0`, 최대: `20000`, 단위: 미터)  **중요**: 중심 좌표값(`x`, `y`) 지정 필수 | X |
| rect | `String` | 사각형의 검색 범위 지정 좌표, 지도 화면 내 검색 등 검색 범위 제한이 필요한 경우 사용(형식: `좌측 X 좌표, 좌측 Y 좌표, 우측 X 좌표, 우측 Y 좌표`) | X |
| page | `Integer` | 결과 페이지 번호(최소: `1`, 최대: `45`, 기본값: `1`) | X |
| size | `Integer` | 한 페이지로 표시할 장소 수(최소: `1`, 최대: `15`, 기본값: `15`) | X |
| sort | `Enum` | 결과 정렬 순서   - `distance`: 중심 좌표로부터의 거리 - `accuracy`: 정확도(기본값)   **중요**: `distance` 정렬 사용 시 중심 좌표값(`x`, `y`) 포함 필수 | X |

##### Enum: CategoryGroupCode

| 값 | 설명 |
| --- | --- |
| MT1 | 대형마트 |
| CS2 | 편의점 |
| PS3 | 어린이집, 유치원 |
| SC4 | 학교 |
| AC5 | 학원 |
| PK6 | 주차장 |
| OL7 | 주유소, 충전소 |
| SW8 | 지하철역 |
| BK9 | 은행 |
| CT1 | 문화시설 |
| AG2 | 중개업소 |
| PO3 | 공공기관 |
| AT4 | 관광명소 |
| AD5 | 숙박 |
| FD6 | 음식점 |
| CE7 | 카페 |
| HP8 | 병원 |
| PM9 | 약국 |

#### 응답

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Content-Type | 응답 데이터 타입, 아래 중 하나   - `content-type: application/json;charset=UTF-8` - `content-type: text/xml;charset=UTF-8` | O |

##### 본문

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| meta | [`Meta`](#키워드로%20장소%20검색#응답#Meta) | 조회 결과 메타 정보 |
| documents | [`Document[]`](#키워드로%20장소%20검색#응답#Document) | 키워드 검색 결과 장소 목록 |

##### Meta

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| total\_count | `Integer` | 검색된 장소 수 |
| pageable\_count | `Integer` | `total_count` 중 노출 가능 장소 수 |
| is\_end | `Boolean` | 현재 페이지가 마지막 페이지인지 여부, 값이 `false`인 경우 다음 요청 시 `page` 값을 증가시켜 다음 페이지 요청 가능 |
| same\_name | [`SameName`](#키워드로%20장소%20검색#응답#SameName) | 검색어(`query`)의 지역 및 키워드 분석 정보 |

##### SameName

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| region | `String[]` | 검색어(`query`)에서 인식된 지역 목록(예: `중앙로 맛집`에서 `중앙로`에 해당하는 지역 목록) |
| keyword | `String` | 검색어(`query`)에서 지역 정보를 제외한 키워드(예: `중앙로 맛집`에서 `맛집`) |
| selected\_region | `String` | 인식된 지역 목록 중 현재 검색에 사용된 지역 정보 |

##### Document

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| id | `String` | 장소 ID |
| place\_name | `String` | 장소명, 업체명 |
| category\_name | `String` | 카테고리 이름 |
| category\_group\_code | `String` | 주요 카테고리 그룹 코드, 없을 경우 빈 문자열(`""`) 반환 |
| category\_group\_name | `String` | 주요 카테고리 그룹명, 없을 경우 빈 문자열(`""`) 반환 |
| phone | `String` | 전화번호 |
| address\_name | `String` | 전체 지번 주소 |
| road\_address\_name | `String` | 전체 도로명 주소 |
| x | `String` | X 좌표값, 경도(Longitude) |
| y | `String` | Y 좌표값, 위도(Latitude) |
| place\_url | `String` | 장소 상세 페이지 URL |
| distance | `String` | 중심 좌표까지의 거리(단위: 미터)  **제공 조건**: 중심 좌표값(`x`, `y`)을 요청에 포함한 경우 |

#### 예제

##### 요청: 서울 강남구 삼성동 20km 반경에서 카카오프렌즈 매장 검색

```shellscript
curl -v -G "https://dapi.kakao.com/v2/local/search/keyword.json" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  --data-urlencode "query=카카오프렌즈" \
  -d "y=37.514322572335935" \
  -d "x=127.06283102249932" \
  -d "radius=20000"
```

##### 응답

```json
// HTTP/1.1 200 OK
// Content-Type: application/json;charset=UTF-8
{
  "meta": {
    "same_name": {
      "region": [],
      "keyword": "카카오프렌즈",
      "selected_region": ""
    },
    "pageable_count": 14,
    "total_count": 14,
    "is_end": true
  },
  "documents": [
    {
      "place_name": "카카오프렌즈 코엑스점",
      "distance": "418",
      "place_url": "http://place.map.kakao.com/26338954",
      "category_name": "가정,생활 > 문구,사무용품 > 디자인문구 > 카카오프렌즈",
      "address_name": "서울 강남구 삼성동 159",
      "road_address_name": "서울 강남구 영동대로 513",
      "id": "26338954",
      "phone": "02-6002-1880",
      "category_group_code": "",
      "category_group_name": "",
      "x": "127.05902969025047",
      "y": "37.51207412593136"
    }
    // ...
  ]
}
```

### 카테고리로 장소 검색

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/local/search/category.${FORMAT}` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

요청한 카테고리 코드에 해당하는 장소 검색 결과를 지정한 정렬 기준으로 반환합니다.

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 경로 변수

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| FORMAT | `Enum` | 응답 형식   - `json`: JSON 형식(기본값) - `xml`: XML 형식 | X |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| category\_group\_code | [`Enum: CategoryGroupCode`](#Enum:%20CategoryGroupCode) | 카테고리 그룹 코드 | O |
| x | `String` | 검색할 중심 좌표의 X값, 경도(Longitude)  **참고**: `radius`와 함께 사용해 중심 좌표와 반경 검색 가능 | X |
| y | `String` | 검색할 중심 좌표의 Y값, 위도(Latitude)  **참고**: `radius`와 함께 사용해 중심 좌표와 반경 검색 가능 | X |
| radius | `Integer` | 중심 좌표부터의 검색 반경 거리(최소: `0`, 최대: `20000`, 단위: 미터)  **중요**: 중심 좌표값(`x`, `y`) 지정 필수 | X |
| rect | `String` | 사각형의 검색 범위 지정 좌표, 지도 화면 내 검색 등 범위 제한이 필요한 경우 사용(형식: `좌측 X 좌표, 좌측 Y 좌표, 우측 X 좌표, 우측 Y 좌표`) | X |
| page | `Integer` | 결과 페이지 번호(최소: `1`, 최대: `45`, 기본값: `1`) | X |
| size | `Integer` | 한 페이지로 표시할 장소의 개수(최소: `1`, 최대: `15`, 기본값: `15`) | X |
| sort | `Enum` | 결과 정렬 순서   - `distance`: 중심 좌표로부터의 거리 - `accuracy`: 정확도(기본값)   **중요**: `distance` 정렬 사용 시 중심 좌표값(`x`, `y`) 포함 필수 | X |

#### 응답

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Content-Type | 응답 데이터 타입, 아래 중 하나   - `content-type: application/json;charset=UTF-8` - `content-type: text/xml;charset=UTF-8` | O |

##### 본문

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| meta | [`Meta`](#카테고리로%20장소%20검색#응답#Meta) | 조회 결과 메타 정보 |
| documents | [`Document[]`](#카테고리로%20장소%20검색#응답#Document) | 카테고리 검색 결과 장소 목록 |

##### Meta

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| total\_count | `Integer` | 검색된 장소 수 |
| pageable\_count | `Integer` | `total_count` 중 노출 가능 장소 수 |
| is\_end | `Boolean` | 현재 페이지가 마지막 페이지인지 여부, 값이 `false`인 경우 다음 요청 시 `page` 값을 증가시켜 다음 페이지 요청 가능 |
| same\_name | [`SameName`](#카테고리로%20장소%20검색#응답#SameName) | 지역 및 키워드 분석 정보, 없을 경우 `null` |

##### SameName

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| region | `String[]` | 인식된 지역 목록(예: `중앙로 맛집`에서 `중앙로`에 해당하는 지역 목록) |
| keyword | `String` | 지역 정보를 제외한 키워드(예: `중앙로 맛집`에서 `맛집`) |
| selected\_region | `String` | 인식된 지역 목록 중 현재 검색에 사용된 지역 정보 |

##### Document

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| id | `String` | 장소 ID |
| place\_name | `String` | 장소명, 업체명 |
| category\_name | `String` | 카테고리 이름 |
| category\_group\_code | `String` | 요청한 카테고리 그룹 코드 |
| category\_group\_name | `String` | 요청한 카테고리 그룹명 |
| phone | `String` | 전화번호 |
| address\_name | `String` | 전체 지번 주소 |
| road\_address\_name | `String` | 전체 도로명 주소 |
| x | `String` | X 좌표값, 경도(Longitude) |
| y | `String` | Y 좌표값, 위도(Latitude) |
| place\_url | `String` | 장소 상세 페이지 URL |
| distance | `String` | 중심 좌표까지의 거리(단위: 미터)  **제공 조건**: 중심 좌표값(`x`, `y`)을 요청에 포함한 경우 |

#### 예제

##### 요청: 서울 강남구 삼성동 20km 반경에서 약국 검색

```shellscript
curl -v -G "https://dapi.kakao.com/v2/local/search/category.json" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  -d "category_group_code=PM9" \
  -d "y=37.514322572335935" \
  -d "x=127.06283102249932" \
  -d "radius=20000"
```

##### 응답

```json
// HTTP/1.1 200 OK
// Content-Type: application/json;charset=UTF-8
{
  "meta": {
    "same_name": null,
    "pageable_count": 11,
    "total_count": 11,
    "is_end": true
  },
  "documents": [
    {
      "place_name": "장생당약국",
      "distance": "",
      "place_url": "http://place.map.kakao.com/16618597",
      "category_name": "의료,건강 > 약국",
      "address_name": "서울 강남구 대치동 943-16",
      "road_address_name": "서울 강남구 테헤란로84길 17",
      "id": "16618597",
      "phone": "02-558-5476",
      "category_group_code": "PM9",
      "category_group_name": "약국",
      "x": "127.05897078335246",
      "y": "37.506051888130386"
    }
    // ...
  ]
}
```

## 경로 조회

### 대중교통 경로 조회

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/routing/publictraffic` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

지정한 출발지와 도착지 좌표의 대중교통 경로를 반환합니다.

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| start\_x | `String` | 출발지 X 좌표 | O |
| start\_y | `String` | 출발지 Y 좌표 | O |
| s\_name | `String` | 출발지 명칭(기본값: `출발`) | X |
| end\_x | `String` | 도착지 X 좌표 | O |
| end\_y | `String` | 도착지 Y 좌표 | O |
| e\_name | `String` | 도착지 명칭(기본값: `도착`) | X |
| input\_coord | `Enum` | 입력 좌표계   - `WGS84`(기본값) - `WTM` - `TM` - `WCONGNAMUL` | X |
| output\_coord | `Enum` | 출력 좌표계   - `WGS84`(기본값) - `WTM` - `TM` - `WCONGNAMUL` | X |

#### 응답

##### 본문

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| status | `Enum` | 대중교통 경로 탐색 결과 코드   - `OK`: 조회 성공 - `STARTNODES_NULL`: 출발지 노드 없음 - `ENDNODES_NULL`: 도착지 노드 없음 - `EQUAL_POINTS`: 출발지와 도착지가 동일 - `INVALID_REQUEST`: 잘못된 요청 - `NO_RESULTS`: 결과 없음 |
| properties | [`Properties`](#Properties) | 경로 조회 결과 속성 |
| routes | [`Route[]`](#대중교통%20경로%20조회#응답#Route) | 대중교통 경로 목록  **중요**: `status`가 `OK`인 경우에만 응답에 포함 |

##### Properties

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| total | `Integer` | 전체 경로 수 |
| bus | `Integer` | 버스 경로 수 |
| subway | `Integer` | 지하철 경로 수 |
| busAndSubway | `Integer` | 버스와 지하철을 이용하는 경로 수 |
| landingURL | `String` | 카카오맵 길찾기 화면 랜딩 URL |

##### Route

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| properties | [`RouteProperties`](#대중교통%20경로%20조회#응답#RouteProperties) | 대중교통 경로 속성 |
| steps | [`Step[]`](#대중교통%20경로%20조회#응답#Step) | 대중교통 경로 단계 목록 |

##### RouteProperties

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| type | `Enum` | 대중교통 경로 타입   - `BUS`: 버스 - `SUBWAY`: 지하철 - `BUS_AND_SUBWAY`: 버스와 지하철 |
| totalDistance | `Integer` | 대중교통 경로 거리(단위: 미터) |
| totalTime | `Integer` | 대중교통 경로 소요 시간(단위: 초(s)) |
| transfers | `Integer` | 대중교통 경로 환승 횟수 |
| fare | [`Fare`](#Fare) | 대중교통 경로 요금 정보 |

##### Fare

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| value | `Integer` | 요금(단위: 원) |
| min | `Integer` | 최소 요금 |
| max | `Integer` | 최대 요금 |

##### Step

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| properties | [`StepProperties`](#대중교통%20경로%20조회#응답#StepProperties) | 대중교통 경로 단계 속성 |
| path | [`Path`](#대중교통%20경로%20조회#응답#Path) | 대중교통 경로 단계 좌표 정보 |

##### StepProperties

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| guidance | `String` | 대중교통 경로 단계 안내 문구 |
| type | `Enum` | 대중교통 경로 단계 타입   - `BUS`: 버스 - `SUBWAY`: 지하철 - `WALKING`: 도보 |
| distance | `Integer` | 대중교통 경로 단계 거리(단위: 미터) |
| time | `Integer` | 대중교통 경로 단계 소요 시간(단위: 초(s)) |
| stops | [`Stop[]`](#Stop) | 대중교통 경로 단계 정류장 목록 |
| vehicles | [`Vehicle[]`](#Vehicle) | 대중교통 경로 단계 차량 목록 |

##### Stop

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| name | `String` | 정류장명 |

##### Vehicle

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| type | `String` | 버스 또는 지하철의 세부 타입 명칭 `간선`, `지선`, `광역`, `순환`, `공항`, `일반`, `좌석`, `급행`, `마을`, `직행`, `외곽`, `시외`, `농어촌`, `한강리버`, `청소년`, `투어`, `직통`, `ITX청춘`, `특급`  **중요**: 세부 타입 명칭은 추가, 변경, 삭제될 수 있음 |
| name | `String` | 차량 이름 |

##### Path

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| points | `Double[][]` | 대중교통 경로 단계 좌표 목록, 내부 배열은 `[x, y]` 형식의 좌표 쌍 (예: `[[127.02700693, 37.49864277], [127.02698289, 37.49863151]]`) |

#### 예제

##### 요청

```shellscript
curl -v -G "https://dapi.kakao.com/v2/routing/publictraffic" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  --data-urlencode "start_x=127.11119217" \
  --data-urlencode "start_y=37.39477123" \
  --data-urlencode "end_x=127.12628814" \
  --data-urlencode "end_y=37.41993056"
```

##### 응답

```json
// HTTP/1.1 200 OK
// Content-Type: application/json;charset=UTF-8
{
  "status": "OK",
  "properties": {
    "total": 15,
    "bus": 9,
    "subway": 1,
    "busAndSubway": 5,
    "landingURL": "https://map.kakao.com/link/by/traffic/%EC%B6%9C%EB%B0%9C,37.39477123,127.11119217/%EB%8F%84%EC%B0%A9,37.41993056,127.12628814"
  },
  "routes": [
    {
      "properties": {
        "type": "BUS",
        "totalDistance": 5013,
        "totalTime": 2115,
        "transfers": 0,
        "fare": {
          "value": 1350
        }
      },
      "steps": [
        {
          "properties": {
            "guidance": "마을 76 (판교역동편 > 성남시청전면)",
            "type": "BUS",
            "distance": 4127,
            "time": 1158,
            "stops": [
              { "name": "판교역동편" },
              { "name": "봇들마을7.8단지.롯데마트판교점" }
              // ...
            ],
            "vehicles": [
              { "name": "76", "type": "마을" }
              // ...
            ]
          },
          "path": {
            "points": [
              [127.11316378, 37.3948816],
              [127.11312974, 37.39488161]
              // ...
            ]
          }
        }
        // ...
      ]
    }
    // ...
  ]
}
```

### 도보 경로 조회

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/routing/walk` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

지정한 출발지와 도착지 좌표의 도보 경로를 반환합니다.

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| start\_x | `String` | 출발지 X 좌표 | O |
| start\_y | `String` | 출발지 Y 좌표 | O |
| via\_x | `String` | 경유지 X 좌표(최대: 5개, 쉼표(`,`)로 구분) | X |
| via\_y | `String` | 경유지 Y 좌표(최대: 5개, 쉼표(`,`)로 구분) | X |
| end\_x | `String` | 도착지 X 좌표 | O |
| end\_y | `String` | 도착지 Y 좌표 | O |
| s\_name | `String` | 출발지 명칭(기본값: `출발`) | X |
| v\_name | `String` | 경유지 명칭(최대: 5개, 쉼표(`,`)로 구분) | X |
| e\_name | `String` | 도착지 명칭(기본값: `도착`) | X |
| input\_coord | `Enum` | 입력 좌표계   - `WGS84`(기본값) - `WTM` - `TM` - `WCONGNAMUL` | X |
| output\_coord | `Enum` | 출력 좌표계   - `WGS84`(기본값) - `WTM` - `TM` - `WCONGNAMUL` | X |
| route\_mode | `Enum` | 탐색 옵션   - `BROAD_FIRST`: 넓은 길 우선(기본값) - `SHORTEST`: 최단 경로 - `ACCESSIBLE`: 편안한 길 | X |

#### 응답

##### 본문

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| status | `Enum` | 경로 탐색 결과 상태값   - `OK`: 조회 성공 - `SAME_POINT`: 출발지와 도착지가 동일 - `START_LINK_NOT_FOUND`: 출발지 주변 도로를 찾을 수 없음 - `END_LINK_NOT_FOUND`: 도착지 주변 도로를 찾을 수 없음 - `TOO_MANY_SEARCH_LINK`: 너무 많은 링크를 탐색함 - `TOO_FAR_AWAY`: 출발지와 도착지가 너무 멀리 떨어져 있음 - `ROUTE_RESULT_NOT_FOUND`: 결과 없음 |
| route | [`Route`](#도보%20경로%20조회#응답#Route) | 전체 경로 정보  **중요**: `status`가 `OK`인 경우에만 응답에 포함 |

##### Route

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| properties | [`RouteProperties`](#도보%20경로%20조회#응답#RouteProperties) | 전체 경로 속성 |
| legs | [`Leg[]`](#Leg) | 경로 구간 목록 |

##### RouteProperties

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| totalDistance | `Integer` | 전체 경로 거리(단위: 미터) |
| totalTime | `Integer` | 전체 경로 소요 시간(단위: 초(s)) |
| landingUrl | `String` | 카카오맵 길찾기 화면 랜딩 URL |

##### Leg

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| properties | [`LegProperties`](#LegProperties) | 경로 구간 속성 |
| steps | [`Step[]`](#도보%20경로%20조회#응답#Step) | 경로 구간 단계 목록 |

##### LegProperties

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| distance | `Integer` | 경로 구간 거리(단위: 미터) |
| time | `Integer` | 경로 구간 소요 시간(단위: 초(s)) |

##### Step

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| properties | [`StepProperties`](#도보%20경로%20조회#응답#StepProperties) | 경로 단계 속성 |
| path | [`Path`](#도보%20경로%20조회#응답#Path) | 경로 단계 좌표 정보 |

##### StepProperties

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| distance | `Integer` | 경로 단계 거리(단위: 미터) |
| guidance | `String` | 경로 단계 안내 문구 |
| time | `Integer` | 경로 단계 소요 시간(단위: 초(s)) |
| x | `Double` | 경로 단계 시작점 X 좌표 |
| y | `Double` | 경로 단계 시작점 Y 좌표 |

##### Path

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| points | `Double[][]` | 경로 단계 좌표 목록, 내부 배열은 `[x, y]` 형식의 좌표 쌍 (예: `[[127.02700693, 37.49864277], [127.02698289, 37.49863151]]`) |

#### 예제

##### 요청

```shellscript
curl -v -G "https://dapi.kakao.com/v2/routing/walk" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  --data-urlencode "start_x=127.11119669891646" \
  --data-urlencode "start_y=37.394776627382875" \
  --data-urlencode "end_x=127.12629039752096" \
  --data-urlencode "end_y=37.4199323570413"
```

##### 응답

```json
// HTTP/1.1 200 OK
// Content-Type: application/json;charset=UTF-8
{
  "route": {
    "properties": {
      "totalDistance": 4025,
      "totalTime": 3914,
      "landingUrl": "https://map.kakao.com/link/by/walk/%EC%B6%9C%EB%B0%9C,37.394776627382875,127.11119669891646/%EB%8F%84%EC%B0%A9,37.4199323570413,127.12629039752096"
    },
    "legs": [
      {
        "properties": {
          "distance": 4025,
          "time": 3914
        },
        "steps": [
          {
            "properties": {
              "distance": 93,
              "guidance": "판교역 1번 출구까지 역사 내 이동",
              "time": 84,
              "x": 127.11119783,
              "y": 37.39477573
            },
            "path": {
              "points": [
                [127.11119783, 37.39477573],
                [127.11119779, 37.39474869],
                [127.1114835, 37.39474572],
                [127.11148211, 37.39533499]
                // ...
              ]
            }
          }
          // ...
        ]
      }
      // ...
    ]
  },
  "status": "OK"
}
```

### 자전거 경로 조회

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/routing/bicycle` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

지정한 출발지와 도착지 좌표의 자전거 경로를 반환합니다.

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| start\_x | `String` | 출발지 X 좌표 | O |
| start\_y | `String` | 출발지 Y 좌표 | O |
| via\_x | `String` | 경유지 X 좌표(최대: 5개, 쉼표(`,`)로 구분) | X |
| via\_y | `String` | 경유지 Y 좌표(최대: 5개, 쉼표(`,`)로 구분) | X |
| end\_x | `String` | 도착지 X 좌표 | O |
| end\_y | `String` | 도착지 Y 좌표 | O |
| s\_name | `String` | 출발지 명칭(기본값: `출발`) | X |
| v\_name | `String` | 경유지 명칭(최대: 5개, 쉼표(`,`)로 구분) | X |
| e\_name | `String` | 도착지 명칭(기본값: `도착`) | X |
| input\_coord | `Enum` | 입력 좌표계   - `WGS84`(기본값) - `WTM` - `TM` - `WCONGNAMUL` | X |
| output\_coord | `Enum` | 출력 좌표계   - `WGS84`(기본값) - `WTM` - `TM` - `WCONGNAMUL` | X |
| route\_mode | `Enum` | 탐색 옵션   - `BIKE_ONLY`: 자전거도로 우선(기본값) - `SHORTEST`: 최단 경로 - `ACCESSIBLE`: 편안한길 | X |

#### 응답

응답은 [도보 경로 조회 API 응답](#도보%20경로%20조회#응답)과 동일합니다.

#### 예제

##### 요청

```shellscript
curl -v -G "https://dapi.kakao.com/v2/routing/bicycle" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  --data-urlencode "start_x=127.11119669891646" \
  --data-urlencode "start_y=37.394776627382875" \
  --data-urlencode "end_x=127.12629039752096" \
  --data-urlencode "end_y=37.4199323570413"
```

##### 응답

```json
// HTTP/1.1 200 OK
// Content-Type: application/json;charset=UTF-8
{
  "route": {
    "properties": {
      "totalDistance": 4155,
      "totalTime": 1242,
      "landingUrl": "https://map.kakao.com/link/by/bicycle/%EC%B6%9C%EB%B0%9C,37.394776627382875,127.11119669891646/%EB%8F%84%EC%B0%A9,37.4199323570413,127.12629039752096"
    },
    "legs": [
      {
        "properties": {
          "distance": 4155,
          "time": 1242
        },
        "steps": [
          {
            "properties": {
              "distance": 76,
              "guidance": "76m 이동",
              "time": 12,
              "x": 127.11143401,
              "y": 37.39488363
            },
            "path": {
              "points": [
                [127.11143401, 37.39488363],
                [127.11145558, 37.39495569],
                [127.11145156, 37.39529448],
                [127.11150469, 37.39532596]
                // ...
              ]
            }
          }
          // ...
        ]
      }
      // ...
    ]
  },
  "status": "OK"
}
```

## 정적 지도 조회

##### 기본 정보

| 메서드 | URL | 인증 방식 |
| --- | --- | --- |
| `GET` | `https://dapi.kakao.com/v2/maps/staticmap` | - [REST API 키](https://developers.kakao.com/docs/ko/app-setting/app#rest-api-key) |

| 요구 사항 | 참고 |
| --- | --- |
| - | - [에러 코드](https://developers.kakao.com/docs/ko/rest-api/error-code) - [FAQ](이해하기.md#FAQ) |

지정한 좌표와 옵션을 반영한 정적 지도 이미지를 생성해 반환합니다.

##### 카카오 CI 로고

- 응답 이미지에 카카오 CI 로고 포함
- `logo_pos` 파라미터로 로고 위치를 조정할 수 있으나 제거 불가

#### 요청

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Authorization | 인증 방식, REST API 키로 인증 요청 `Authorization: KakaoAK ${REST_API_KEY}` | O |

##### 쿼리 파라미터

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| center | `String` | 지도 중심 좌표, 쉼표(`,`)로 구분한 `X,Y` 형식(예: `127.1105,37.3955`) | X\* |
| markers | `String` | 마커 정보, 마커 구성 방법은 [`markers` 내부 파라미터](#markers%20내부%20파라미터) 확인 | X\* |
| size | `String` | 이미지 크기, `{WIDTH}x{HEIGHT}` 형식(최대: `2048x1024`) | O |
| format | `Enum` | 응답 이미지 포맷   - `png`: PNG 이미지(기본값) - `jpg`: JPEG 이미지 | X |
| logo\_pos | `Enum` | 카카오 CI 로고 위치   - `BOTTOM_LEFT`: 왼쪽 아래(기본값) - `BOTTOM_RIGHT`: 오른쪽 아래 - `TOP_LEFT`: 왼쪽 위 - `TOP_RIGHT`: 오른쪽 위 | X |
| scale | `Integer` | 이미지 배율   - `1`: 1배 - `2`: 2배(기본값)   **참고**: `scale`이 `2`인 경우 응답 이미지는 `size`의 2배 크기 | X |
| lv | `Integer` | 지도 줌 레벨(최소: `1`, 최대: `15`, 기본값: `3`) | X |
| coord | `Enum` | 요청에 적용할 좌표계   - `WGS84`(기본값) - `WCONGNAMUL` - `WTM` - `TM` | X |

\* `center`, `markers` 중 1개 이상 필수

##### markers 내부 파라미터

`markers`의 값은 콜론(`:`)으로 키와 값을 구분하고, 파라미터는 파이프(`|`)로 연결합니다. 각 마커간 연결은 앰퍼샌드(`&`)로 연결하며, 최대 5개까지 연결할 수 있습니다. 아래 파라미터 표와 예제를 참고합니다.

| 이름 | 타입 | 설명 | 필수 |
| --- | --- | --- | --- |
| location | `String` | 마커 좌표, 쉼표(`,`)로 구분한 `X,Y` 형식 (예: `127.1105,37.3955`) | O |
| option | `Boolean` | 지도 영역(`center`, `lv`) 자동 계산 시 마커 제외 여부   - `true`: 영역 계산에서 제외 - `false`: 영역 계산에 포함(기본값) | X |

```text
markers=location:127.1105,37.3955|option:false&markers=location:127.1120,37.3970|option:false
```

#### 응답

##### 헤더

| 이름 | 설명 | 필수 |
| --- | --- | --- |
| Content-Type | 응답 이미지 형식, 요청의 `format`이 `jpg`인 경우 `image/jpeg` `Content-Type: image/png` | O |

##### 본문

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| - | `Binary` | 정적 지도 이미지 형식은 요청의 `format` 값에 따르며, 응답 `Content-Type` 헤더로 확인 |

#### 예제

##### 요청

```shellscript
curl -v -G "https://dapi.kakao.com/v2/maps/staticmap" \
  -H "Authorization: KakaoAK ${REST_API_KEY}" \
  --data-urlencode "center=127.1105,37.3955" \
  --data-urlencode "size=640x480" \
  --data-urlencode "markers=location:127.1105,37.3955|option:false"
```

##### 응답

```http
HTTP/1.1 200 OK
Content-Type: image/png

<바이너리 이미지 데이터>
```

## 더 보기

- [REST API 레퍼런스](https://developers.kakao.com/docs/ko/rest-api/reference)

### 도움이 되었나요?
