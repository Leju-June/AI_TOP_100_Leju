from datetime import datetime

import pytest

from eodiro import commands as c
from eodiro.config import KST

NOON = datetime(2026, 10, 28, 12, 0, tzinfo=KST)
EVENING = datetime(2026, 10, 28, 19, 0, tzinfo=KST)


@pytest.mark.parametrize("text, expected", [
    ("@어디로 미금역", c.Route("미금역", c.Mode.TRANSIT)),
    ("@어디로 미금역까지 얼마나 남았어?", c.Route("미금역", c.Mode.TRANSIT)),
    ("@어디로 미금역까지 버스로", c.Route("미금역", c.Mode.BUS)),
    ("@어디로 미금역 지하철로 가는 길", c.Route("미금역", c.Mode.SUBWAY)),
    ("@어디로 강남역까지 걸어서 몇 분 걸려?", c.Route("강남역", c.Mode.WALK)),
    ("@어디로 맛집 추가 을지로 골뱅이", c.AddRestaurant("을지로 골뱅이")),
    ("@어디로 맛집 삭제 2", c.RemoveRestaurant("2")),
    ("@어디로 맛집 리스트", c.ListRestaurants()),
    ("@어디로 리스트", c.ListRestaurants()),
    ("@어디로 점메추", c.Recommend("점심", False)),
    ("@어디로 저녁 메뉴 추천해줘", c.Recommend("저녁", False)),
    ("@어디로 아무대나 점메추", c.Recommend("점심", True)),
    ("@어디로 아무데나 저메추", c.Recommend("저녁", True)),
    ("@어디로", c.Help()),
    ("@어디로 도움말", c.Help()),
])
def test_parse(text, expected):
    assert c.parse(text, NOON) == expected


def test_button_messages_without_mention():
    # 카드 버튼은 멘션 없이 명령 문장만 보낸다.
    assert c.parse("맛집 리스트", NOON) == c.ListRestaurants()
    assert c.parse("맛집 추가", NOON) == c.AddRestaurant("")
    assert c.parse("아무대나 점메추", NOON) == c.Recommend("점심", True)


def test_menu_recommend_uses_time_of_day():
    assert c.parse("@어디로 메뉴 추천", NOON) == c.Recommend("점심", False)
    assert c.parse("@어디로 뭐 먹지", EVENING) == c.Recommend("저녁", False)
