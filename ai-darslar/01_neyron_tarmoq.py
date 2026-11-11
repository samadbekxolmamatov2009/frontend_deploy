"""
1-dars: Noldan neyron tarmoq (faqat numpy bilan)

Vazifa: tarmoqqa XOR amalini o'rgatamiz.
    0 XOR 0 = 0
    0 XOR 1 = 1
    1 XOR 0 = 1
    1 XOR 1 = 0

Biz qoidani kodga YOZMAYMIZ. Tarmoq uni misollardan o'zi topadi.
Har qanday sun'iy intellekt (ChatGPT, Claude ham) aynan shu 4 qadamni takrorlaydi:

    1. Taxmin qilish        (forward pass)
    2. Xatoni o'lchash      (loss)
    3. Aybdorni topish      (backpropagation)
    4. Og'irliklarni tuzatish (gradient descent)

Ishga tushirish:  python3 ai-darslar/01_neyron_tarmoq.py
"""

import numpy as np

rng = np.random.default_rng(42)  # har safar bir xil natija chiqishi uchun

# --- Ma'lumot: kirishlar (X) va to'g'ri javoblar (y) ---
X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
y = np.array([[0], [1], [1], [0]], dtype=float)

# --- Tarmoq tuzilishi: 2 kirish -> 4 yashirin neyron -> 1 chiqish ---
# Og'irliklar (W) va siljishlar (b) - tarmoqning "bilimi".
# Boshida ular tasodifiy sonlar, ya'ni tarmoq hech narsa bilmaydi.
YASHIRIN = 4
W1 = rng.normal(0, 1, size=(2, YASHIRIN))
b1 = np.zeros((1, YASHIRIN))
W2 = rng.normal(0, 1, size=(YASHIRIN, 1))
b2 = np.zeros((1, 1))


def sigmoid(z):
    """Istalgan sonni 0 va 1 orasiga siqadi."""
    return 1 / (1 + np.exp(-z))


def taxmin(X):
    """1-qadam: kirishdan chiqishgacha hisoblash."""
    h = np.tanh(X @ W1 + b1)      # yashirin qatlam
    chiqish = sigmoid(h @ W2 + b2)  # yakuniy javob (0..1)
    return h, chiqish


ORGANISH_TEZLIGI = 0.5
DAVRLAR = 5000

print("O'qitishdan OLDIN (tasodifiy taxminlar):")
for kirish, p in zip(X, taxmin(X)[1]):
    print(f"  {kirish.astype(int)} -> {p[0]:.3f}")
print()

for davr in range(DAVRLAR + 1):
    # 1. Taxmin
    h, chiqish = taxmin(X)

    # 2. Xato: taxmin to'g'ri javobdan qanchalik uzoq?
    xato = np.mean((chiqish - y) ** 2)

    # 3. Backpropagation: har bir og'irlik xatoga qancha hissa qo'shganini
    #    zanjir qoidasi (hosila) orqali orqadan oldinga hisoblaymiz.
    d_chiqish = 2 * (chiqish - y) / len(X) * chiqish * (1 - chiqish)
    d_W2 = h.T @ d_chiqish
    d_b2 = d_chiqish.sum(axis=0, keepdims=True)
    d_h = d_chiqish @ W2.T * (1 - h**2)
    d_W1 = X.T @ d_h
    d_b1 = d_h.sum(axis=0, keepdims=True)

    # 4. Tuzatish: har bir og'irlikni xatoni kamaytiradigan tomonga ozgina suramiz.
    W1 -= ORGANISH_TEZLIGI * d_W1
    b1 -= ORGANISH_TEZLIGI * d_b1
    W2 -= ORGANISH_TEZLIGI * d_W2
    b2 -= ORGANISH_TEZLIGI * d_b2

    if davr % 1000 == 0:
        print(f"davr {davr:>5}   xato = {xato:.5f}")

print("\nO'qitishdan KEYIN:")
togri = 0
for kirish, p, javob in zip(X, taxmin(X)[1], y):
    belgi = "to'g'ri" if round(p[0]) == javob[0] else "XATO"
    togri += belgi == "to'g'ri"
    print(f"  {kirish.astype(int)} -> {p[0]:.3f}   (kutilgan: {int(javob[0])})  {belgi}")
print(f"\nNatija: {togri}/4 to'g'ri")
