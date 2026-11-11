"""O'yinni bitta faylga yig'adi: oyin.html (o'yin kodi) + three.html (3D kutubxona) -> ../index.html

Ishga tushirish:  python3 oyinlar/poligon/manba/yigish.py
"""
from pathlib import Path

here = Path(__file__).parent
game = (here / "oyin.html").read_text(encoding="utf-8")
three = (here / "three.html").read_text(encoding="utf-8")
assert game.count("<!--THREE-->") == 1
(here.parent / "index.html").write_text(game.replace("<!--THREE-->", three), encoding="utf-8")
print("Tayyor:", here.parent / "index.html")
