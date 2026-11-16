"""Tests for phone.ui module (pure parsing, no device needed)."""

from __future__ import annotations

from phone.ui import Bounds, parse_bounds, parse_ui_xml

SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout"
        package="com.example" bounds="[0,0][1080,2340]" clickable="false"
        enabled="true" focused="false">
    <node index="0" text="Sign in" resource-id="com.example:id/login"
          class="android.widget.Button" package="com.example"
          bounds="[100,500][900,600]" clickable="true" enabled="true"
          focused="false" content-desc="" />
    <node index="1" text="" resource-id="com.example:id/toggle"
          class="android.view.View" package="com.example"
          bounds="[863,757][990,831]" clickable="false" enabled="true"
          focused="false" content-desc="Enable calls" />
  </node>
</hierarchy>
"""


def test_parse_bounds():
    b = parse_bounds("[863,757][990,831]")
    assert b == Bounds(863, 757, 990, 831)
    assert b.center == (926, 794)
    assert parse_bounds("") is None
    assert parse_bounds("garbage") is None


def test_parse_ui_xml_flat():
    nodes = parse_ui_xml(SAMPLE_XML)
    assert len(nodes) == 3
    btn = nodes[1]
    assert btn.text == "Sign in"
    assert btn.resource_id == "com.example:id/login"
    assert btn.clickable is True
    assert btn.bounds.center == (500, 550)
    # children tracked on root
    assert len(nodes[0].children) == 2


def test_find_by_text():
    nodes = parse_ui_xml(SAMPLE_XML)
    # exercise UiNode.matches directly
    assert nodes[1].matches(text="Sign")
    assert not nodes[1].matches(text="Sign", contains=False)
    assert nodes[1].matches(text="Sign in", contains=False)
    assert nodes[2].matches(desc="Enable")
    assert nodes[2].matches(resource_id="toggle")
    assert not nodes[2].matches(class_name="Button")
