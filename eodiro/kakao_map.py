"""카카오맵 / 카카오모빌리티 REST API 클라이언트.

명세: kakaomap_설명서/REST API.md, kakaomap_설명서/웹 지도 가이드.md
자동차 길찾기는 카카오모빌리티 API(apis-navi.kakaomobility.com)이며 로컬 문서 사본이 없다.
"""
from dataclasses import dataclass
from urllib.parse import quote

import httpx

DAPI_URL = "https://dapi.kakao.com"
NAVI_URL = "https://apis-navi.kakaomobility.com"

CATEGORY_RESTAURANT = "FD6"
CATEGORY_CAFE = "CE7"


class KakaoMapError(Exception):
    pass


@dataclass(frozen=True)
class Point:
    lng: float  # x
    lat: float  # y


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    category: str
    address: str
    point: Point
    url: str
    distance_m: int | None = None

    @property
    def short_category(self) -> str:
        """'음식점 > 한식 > 국밥' -> '국밥'"""
        return self.category.split(">")[-1].strip() if self.category else ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "category": self.category, "address": self.address,
            "lng": self.point.lng, "lat": self.point.lat, "url": self.url,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Place":
        return cls(d["id"], d["name"], d["category"], d["address"], Point(d["lng"], d["lat"]), d["url"])

    @classmethod
    def from_document(cls, doc: dict) -> "Place":
        dist = doc.get("distance")
        return cls(
            id=doc["id"],
            name=doc["place_name"],
            category=doc.get("category_name", ""),
            address=doc.get("road_address_name") or doc.get("address_name", ""),
            point=Point(float(doc["x"]), float(doc["y"])),
            url=doc.get("place_url", ""),
            distance_m=int(dist) if dist else None,
        )


def map_link(mode: str, origin_name: str, origin: Point, dest_name: str, dest: Point) -> str:
    """카카오맵 길찾기 바로가기 URL. mode: car | traffic | walk | bicycle"""
    def seg(name: str, p: Point) -> str:
        return f"{quote(name)},{p.lat},{p.lng}"

    return f"https://map.kakao.com/link/by/{mode}/{seg(origin_name, origin)}/{seg(dest_name, dest)}"


class KakaoMapClient:
    def __init__(self, rest_api_key: str, http: httpx.AsyncClient):
        self.http = http
        self.headers = {"Authorization": f"KakaoAK {rest_api_key}"}

    async def _get(self, url: str, params: dict) -> dict:
        resp = await self.http.get(url, params=params, headers=self.headers, timeout=10)
        if resp.status_code != 200:
            raise KakaoMapError(f"{url} {resp.status_code} {resp.text[:200]}")
        return resp.json()

    async def search_keyword(self, query: str, *, category: str | None = None, near: Point | None = None,
                             size: int = 5) -> list[Place]:
        params = {"query": query, "size": size}
        if category:
            params["category_group_code"] = category
        if near:
            params.update(x=near.lng, y=near.lat)
        data = await self._get(f"{DAPI_URL}/v2/local/search/keyword.json", params)
        return [Place.from_document(d) for d in data.get("documents", [])]

    async def search_category(self, category: str, near: Point, *, radius: int = 1000,
                              size: int = 15) -> list[Place]:
        params = {"category_group_code": category, "x": near.lng, "y": near.lat,
                  "radius": radius, "size": size, "sort": "distance"}
        data = await self._get(f"{DAPI_URL}/v2/local/search/category.json", params)
        return [Place.from_document(d) for d in data.get("documents", [])]

    async def transit_route(self, start: Point, end: Point) -> dict:
        return await self._get(f"{DAPI_URL}/v2/routing/publictraffic",
                               {"start_x": start.lng, "start_y": start.lat, "end_x": end.lng, "end_y": end.lat})

    async def walk_route(self, start: Point, end: Point) -> dict:
        return await self._get(f"{DAPI_URL}/v2/routing/walk",
                               {"start_x": start.lng, "start_y": start.lat, "end_x": end.lng, "end_y": end.lat})

    async def car_route(self, start: Point, end: Point) -> dict:
        return await self._get(f"{NAVI_URL}/v1/directions",
                               {"origin": f"{start.lng},{start.lat}", "destination": f"{end.lng},{end.lat}"})
