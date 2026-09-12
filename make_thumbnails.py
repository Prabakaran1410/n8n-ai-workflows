"""Catalog thumbnails for the automation offer — poster logic, not documentation.

Same palette and construction as the document-extraction offer's assets, on purpose:
two listings from one seller should look like one seller.

What differs is the metaphor. A buyer shopping this category is scrolling, and the
node-graph shape is recognisable before a single word is read — so the graph is the
picture, and the headline only has to land the one idea the competing listings do not
claim: that it tells you when it breaks.

Canvas is 1600x1200. Upwork rejects under 1000x750, and that minimum is exactly 4:3,
so a 16:9 image would be cropped even if it passed the size check.

    python make_thumbnails.py
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ASSETS = pathlib.Path("assets")
W, H = 1600, 1200
F = "C:/Windows/Fonts/"

NAVY_TOP = (13, 20, 41)
NAVY_BOT = (26, 49, 92)
LIME = (61, 220, 151)
AMBER = (255, 183, 61)
CORAL = (255, 106, 92)
WHITE = (255, 255, 255)
FOG = (166, 180, 204)
CHIP = (44, 64, 104)
NODE = (247, 249, 253)
WIRE = (118, 146, 196)

BLACK_F, BOLD_F, REG_F = "ariblk.ttf", "arialbd.ttf", "arial.ttf"
MONO_F, MONOB_F = "consola.ttf", "consolab.ttf"


def f(name, size):
    return ImageFont.truetype(F + name, size)


def gradient(w, h, top, bottom):
    base = Image.new("RGB", (w, h), top)
    d = ImageDraw.Draw(base)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)],
               fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return base


def glow(img, xy, radius, colour, strength=70):
    layer = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([xy[0] - radius, xy[1] - radius, xy[0] + radius, xy[1] + radius], fill=colour)
    layer = layer.filter(ImageFilter.GaussianBlur(radius // 2))
    return Image.blend(img, Image.blend(img, layer, 1.0), strength / 255)


def card(size, radius=18, fill=WHITE):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius,
                                         fill=fill + (255,))
    return im


def drop(base, layer, xy, blur=26, alpha=150, offset=(10, 18)):
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    solid = Image.new("RGBA", layer.size, (0, 0, 0, alpha))
    sh.paste(solid, (xy[0] + offset[0], xy[1] + offset[1]), layer.split()[3])
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    base.alpha_composite(layer, xy)


def pill(d, xy, text, font, bg, fg, padx=18, pady=10, radius=999):
    x, y = xy
    w = d.textlength(text, font=font)
    d.rounded_rectangle([x, y, x + w + padx * 2, y + font.size + pady * 2], radius, fill=bg)
    d.text((x + padx, y + pady - 1), text, font=font, fill=fg)
    return x + w + padx * 2


def backdrop():
    img = gradient(W, H, NAVY_TOP, NAVY_BOT)
    img = glow(img, (1310, 330), 520, (30, 90, 130), 55)
    img = glow(img, (190, 1070), 440, (20, 80, 70), 40)
    return img.convert("RGBA")


# --------------------------------------------------------------------------
# The node graph. This is the one thing on the image doing recognition work, so
# it is drawn properly rather than sketched: real rounded cards, a coloured
# icon tile, a label under each node, and wires that route around corners the
# way n8n draws them.
# --------------------------------------------------------------------------

NW, NH = 128, 92


def node(d, x, y, tile, glyph, label, label2=None, ring=None):
    """One node, centred on (x, y). Returns its left/right wire anchors."""
    left, top = x - NW // 2, y - NH // 2
    if ring:
        d.rounded_rectangle([left - 7, top - 7, left + NW + 7, top + NH + 7], 26,
                            outline=ring, width=5)
    d.rounded_rectangle([left, top, left + NW, top + NH], 20, fill=NODE)
    d.rounded_rectangle([left + 30, top + 16, left + NW - 30, top + NH - 22], 16, fill=tile)

    if glyph == "tri":
        # Drawn, not typed: Arial has no warning glyph, and "/!\\" reads as a road sign.
        cy = top + NH // 2 - 8
        d.polygon([(x, cy - 19), (x + 21, cy + 17), (x - 21, cy + 17)], fill=WHITE)
        d.line([x, cy - 4, x, cy + 7], fill=tile, width=5)
        d.ellipse([x - 2, cy + 11, x + 3, cy + 16], fill=tile)
    else:
        gf = f(BLACK_F, 34)
        gw = d.textlength(glyph, font=gf)
        d.text((x - gw / 2, top + 22), glyph, font=gf, fill=WHITE)

    lf = f(BOLD_F, 21)
    for i, line in enumerate([label, label2] if label2 else [label]):
        lw = d.textlength(line, font=lf)
        d.text((x - lw / 2, top + NH + 14 + i * 26), line, font=lf, fill=WHITE)
    return (left - 4, y), (left + NW + 4, y)


def wire(d, a, b, colour=WIRE, width=6, dot=True, mx=None):
    """Right-angle routing with a mid vertical, as n8n draws its connections."""
    (x1, y1), (x2, y2) = a, b
    if y1 == y2:
        d.line([x1, y1, x2, y2], fill=colour, width=width)
    else:
        mx = mx if mx is not None else (x1 + x2) // 2
        d.line([x1, y1, mx, y1], fill=colour, width=width)
        d.line([mx, y1, mx, y2], fill=colour, width=width)
        d.line([mx, y2, x2, y2], fill=colour, width=width)
    if dot:
        d.ellipse([x2 - 9, y2 - 9, x2 + 9, y2 + 9], fill=colour)


def slack_card(width, title, title_col, lines, accent, scale=1.0):
    """A mock Slack message. The alert IS the product here, so it gets drawn to look
    like one rather than being described in a caption."""
    S = scale
    pad = int(26 * S)
    tf, bf, mf = f(BLACK_F, int(23 * S)), f(REG_F, int(19 * S)), f(MONOB_F, int(18 * S))
    lh = int(30 * S)
    h = int(96 * S) + len(lines) * lh + pad

    c = card((width, h), int(18 * S))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([0, 0, int(11 * S), h], 0, fill=accent + (255,))
    d.rectangle([0, int(10 * S), int(11 * S), h - int(10 * S)], fill=accent + (255,))

    d.text((pad + int(12 * S), int(24 * S)), title, font=tf, fill=title_col + (255,))
    y = int(72 * S)
    for text, style in lines:
        font = {"b": f(BOLD_F, int(19 * S)), "m": mf}.get(style, bf)
        col = {"b": (24, 33, 58), "m": (120, 70, 10), "d": (110, 124, 150)}.get(style, (48, 60, 86))
        d.text((pad + int(12 * S), y), text, font=font, fill=col + (255,))
        y += lh
    return c


# --------------------------------------------------------------------------


def main_thumb():
    """The click decision. Headline + the graph, with the error branch in coral."""
    img = backdrop()
    d = ImageDraw.Draw(img)
    M = 78

    d.text((M + 2, 74), "A I   W O R K F L O W   A U T O M A T I O N",
           font=f(BOLD_F, 25), fill=LIME)
    d.text((M, 120), "IT TELLS YOU", font=f(BLACK_F, 88), fill=WHITE)
    d.text((M, 222), "WHEN IT BREAKS.", font=f(BLACK_F, 88), fill=LIME)

    d.text((M + 2, 348), "Most automations fail quietly weeks after handover.",
           font=f(REG_F, 31), fill=FOG)
    d.text((M + 2, 392), "Every one I build has an alert on the failure path.",
           font=f(REG_F, 31), fill=FOG)

    x = M
    for label in ("n8n", "ZAPIER", "MAKE", "PYTHON"):
        x = pill(d, (x, 456), label, f(BOLD_F, 22), CHIP, WHITE) + 14

    # The graph. Kept to five nodes: legible at 290px, and it still tells the story.
    row = 672
    a_in, a_out = node(d, 190, row, (74, 108, 180), "@", "Email in")
    b_in, b_out = node(d, 430, row, (108, 92, 196), "{ }", "Read it")
    c_in, c_out = node(d, 670, row, (36, 60, 110), "?", "Sure enough?")
    ok_in, _ = node(d, 960, row - 130, (34, 160, 110), "=", "Post to sheet")
    hu_in, _ = node(d, 960, row + 130, AMBER, "!", "Ask a human")
    er_in, _ = node(d, 1310, row + 130, CORAL, "tri", "Alert on failure",
                    ring=CORAL)

    wire(d, a_out, b_in)
    wire(d, b_out, c_in)
    wire(d, c_out, ok_in, LIME)
    wire(d, c_out, hu_in, AMBER)
    wire(d, (960 + NW // 2 + 4, row + 130), er_in, CORAL)

    d2 = ImageDraw.Draw(img)
    end = pill(d2, (M, 1060), "FROM  $120", f(BLACK_F, 38), AMBER, (40, 26, 0),
               padx=30, pady=16)
    d2.text((end + 26, 1080), "delivered in 3 days", font=f(BOLD_F, 26), fill=FOG)
    d2.text((W - 600, 1072), "Retries  ·  error alerts  ·  heartbeat",
            font=f(BOLD_F, 24), fill=WHITE)
    d2.text((W - 600, 1108), "You find out from an alert, not a customer.",
            font=f(REG_F, 22), fill=FOG)

    ASSETS.mkdir(exist_ok=True)
    img.convert("RGB").save(ASSETS / "thumb-main.png")
    print("  assets/thumb-main.png")


def alert_thumb():
    """The proof. An actual failure alert, because everyone else says 'reliable'."""
    img = backdrop()
    d = ImageDraw.Draw(img)
    M = 78

    d.text((M + 2, 74), "W H E N   I T   G O E S   W R O N G",
           font=f(BOLD_F, 25), fill=CORAL)
    d.text((M, 120), "SILENCE IS", font=f(BLACK_F, 90), fill=WHITE)
    d.text((M, 224), "THE ENEMY.", font=f(BLACK_F, 90), fill=CORAL)

    d.text((M + 2, 360), "A broken workflow does not announce itself.", font=f(REG_F, 31), fill=FOG)
    d.text((M + 2, 404), "So mine are built to announce it for you.", font=f(REG_F, 31), fill=FOG)

    for i, (title, body) in enumerate([
        ("Error alerts", "names the exact step that failed"),
        ("Automatic retries", "a network blip does not become an outage"),
        ("Daily heartbeat", "catches a workflow that stopped running at all"),
    ]):
        y = 490 + i * 96
        d.ellipse([M + 2, y, M + 34, y + 32], fill=LIME)
        d.line([M + 11, y + 16, M + 18, y + 24], fill=NAVY_TOP, width=5)
        d.line([M + 18, y + 24, M + 27, y + 9], fill=NAVY_TOP, width=5)
        d.text((M + 56, y - 2), title, font=f(BLACK_F, 31), fill=WHITE)
        d.text((M + 56, y + 38), body, font=f(REG_F, 24), fill=FOG)

    alert = slack_card(660, "Invoice intake failed", CORAL, [
        ("Stopped at: Extract document", "b"),
        ("connect ETIMEDOUT after 3 tries", "m"),
        ("Open the failed run", "d"),
        ("07:14  ·  nothing was written", "d"),
    ], CORAL, scale=1.25)
    drop(img, alert, (860, 470), blur=34, alpha=175)

    d.text((880, 830), "The alert a client actually gets.", font=f(BOLD_F, 27), fill=WHITE)
    d.text((880, 872), "Not a stack trace. Not a muted channel.", font=f(REG_F, 24), fill=FOG)

    d.text((880, 1062), "Slack and email, so a Slack outage", font=f(BOLD_F, 25), fill=WHITE)
    d.text((880, 1098), "does not hide the alert about itself.", font=f(REG_F, 23), fill=FOG)

    pill(d, (M, 1058), "ERROR HANDLING ON EVERY TIER", f(BLACK_F, 30), LIME,
         (8, 40, 28), padx=28, pady=16)

    img.convert("RGB").save(ASSETS / "thumb-alert.png")
    print("  assets/thumb-alert.png")


def review_thumb():
    """The AI-trust objection, answered with the review message rather than a promise."""
    img = backdrop()
    d = ImageDraw.Draw(img)
    M = 78

    d.text((M + 2, 74), "A I   S T E P S ,   F E N C E D   I N",
           font=f(BOLD_F, 25), fill=AMBER)
    d.text((M, 120), "IT ASKS", font=f(BLACK_F, 96), fill=WHITE)
    d.text((M, 230), "BEFORE IT", font=f(BLACK_F, 96), fill=WHITE)
    d.text((M, 340), "GUESSES.", font=f(BLACK_F, 96), fill=AMBER)

    d.text((M + 2, 486), "Where the AI is unsure, nothing is written.", font=f(REG_F, 31), fill=FOG)
    d.text((M + 2, 530), "A person is asked, and told exactly why.", font=f(REG_F, 31), fill=FOG)

    review = slack_card(700, "Needs a look before the books", AMBER, [
        ("Hartley Medical  ·  HMS-114-2026", "b"),
        ("Amount: USD 901.39", ""),
        ("invoice_date '03/05/2026'  (0.85)", "m"),
        ("3 May or March 5? Ambiguous.", "m"),
        ("Nothing written. Confirm to post.", "d"),
    ], AMBER, scale=1.3)
    drop(img, review, (800, 560), blur=34, alpha=175)

    d.text((M, 640), "Arithmetic is checked", font=f(BLACK_F, 40), fill=WHITE)
    d.text((M, 692), "in code, never by the AI.", font=f(BLACK_F, 40), fill=LIME)
    d.text((M, 766), "The model reads. Plain code proves", font=f(REG_F, 27), fill=FOG)
    d.text((M, 802), "the numbers add up before anything", font=f(REG_F, 27), fill=FOG)
    d.text((M, 838), "reaches your spreadsheet.", font=f(REG_F, 27), fill=FOG)

    d.text((820, 960), "The message a person actually receives,", font=f(BOLD_F, 27), fill=WHITE)
    d.text((820, 1000), "naming the field and what it guessed.", font=f(REG_F, 24), fill=FOG)

    pill(d, (M, 1058), "CONFIDENCE SCORE ON EVERY FIELD", f(BLACK_F, 28), LIME,
         (8, 40, 28), padx=26, pady=15)

    img.convert("RGB").save(ASSETS / "thumb-review.png")
    print("  assets/thumb-review.png")


def flow_gallery():
    """Gallery slide for someone who already clicked: the whole graph, labelled.

    This is the fallback for the real n8n canvas screenshot, and the thing to put in
    front of a client who wants to see the shape of what they are buying.
    """
    img = backdrop()
    d = ImageDraw.Draw(img)
    M = 78

    d.text((M + 2, 66), "W H A T   Y O U   A C T U A L L Y   G E T",
           font=f(BOLD_F, 25), fill=LIME)
    d.text((M, 112), "THE WHOLE WORKFLOW", font=f(BLACK_F, 62), fill=WHITE)
    d.text((M + 2, 200), "Yours to keep, edit and run. No lock-in.",
           font=f(REG_F, 29), fill=FOG)

    row = 430
    _, a_out = node(d, 180, row, (74, 108, 180), "@", "Email arrives")
    b_in, b_out = node(d, 420, row, (36, 60, 110), "?", "PDF attached?")
    ig_in, _ = node(d, 640, row + 235, (70, 84, 116), "-", "Ignore, not", "a failure")
    c_in, c_out = node(d, 700, row, (108, 92, 196), "{ }", "Extract", "3 retries")
    s_in, s_out = node(d, 960, row, (36, 60, 110), "?", "Sure enough?")
    ok_in, _ = node(d, 1250, row - 140, (34, 160, 110), "=", "Append to sheet")
    hu_in, _ = node(d, 1250, row + 140, AMBER, "!", "Ask a human")

    wire(d, a_out, b_in)
    wire(d, b_out, c_in)
    wire(d, b_out, ig_in, (70, 84, 116), mx=b_out[0] + 26)
    wire(d, c_out, s_in)
    wire(d, s_out, ok_in, LIME)
    wire(d, s_out, hu_in, AMBER)

    er_in, _ = node(d, 1000, row + 235, CORAL, "tri", "If a step fails",
                    "you hear about it", ring=CORAL)
    wire(d, c_out, er_in, CORAL, mx=c_out[0] + 26)

    y = 872
    for title, body, col in [
        ("Retries with backoff", "A rate limit or a network blip recovers on its own.", LIME),
        ("Error workflow", "Any failure names the step and posts it to Slack and email.", CORAL),
        ("Heartbeat", "Catches the failure no error can: it stopped running at all.", AMBER),
    ]:
        d.rounded_rectangle([M, y, M + 9, y + 62], 5, fill=col)
        d.text((M + 32, y - 2), title, font=f(BLACK_F, 28), fill=WHITE)
        d.text((M + 32, y + 36), body, font=f(REG_F, 23), fill=FOG)
        y += 92

    img.convert("RGB").save(ASSETS / "gallery-flow.png")
    print("  assets/gallery-flow.png")


if __name__ == "__main__":
    main_thumb()
    alert_thumb()
    review_thumb()
    flow_gallery()
