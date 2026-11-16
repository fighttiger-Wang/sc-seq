#import "@preview/cetz:0.3.4": canvas, draw

#let font-name = "__FONT__"
#let figure-title = "__TITLE__"
#let subtitle = "__SUBTITLE__"
#let section-title = "__SECTION_TITLE__"
#let comparison-1 = "__COMPARISON_1__"
#let comparison-2 = "__COMPARISON_2__"
#let hub-label = "__HUB_LABEL__"
#let hub-line-1 = "__HUB_LINE_1__"
#let hub-line-2 = "__HUB_LINE_2__"
#let hub-combined = hub-line-1 + "　　" + hub-line-2
#let hub-note = "__HUB_NOTE__"
#let outcome = "__OUTCOME__"
#let footer = "__FOOTER__"

#set page(width: 842pt, height: 595pt, margin: 0pt, fill: white)
#set text(font: font-name, size: 10pt, fill: rgb("#172033"))

#let navy = rgb("#17263C")
#let burgundy = rgb("#8B1E3F")
#let blue = rgb("#2F6FA5")
#let amber = rgb("#B96A17")
#let green = rgb("#39745A")
#let ink = rgb("#172033")
#let muted = rgb("#5D6A7C")
#let line-color = rgb("#C8D1DC")

#canvas(length: 1pt, {
  import draw: *
  let card(x, y, w, h, tag, title, body, fill-color, stroke-color, accent-color) = {
    rect((x, y), (x + w, y + h), radius: 10, fill: fill-color, stroke: 1.1pt + stroke-color)
    rect((x, y), (x + 5, y + h), radius: (left: 10, right: 0), fill: accent-color, stroke: none)
    content((x + 16, y + h - 16), text(font: font-name, size: 8pt, weight: "bold", fill: accent-color)[#tag], anchor: "north-west")
    content((x + 16, y + h - 39), text(font: font-name, size: 12.5pt, weight: "bold", fill: ink)[#title], anchor: "north-west")
    content((x + 16, y + 17), text(font: font-name, size: 8pt, fill: muted)[#body], anchor: "west")
  }

  rect((0, 0), (842, 510), fill: rgb("#F5F7FA"), stroke: none)
  rect((0, 510), (842, 595), fill: navy, stroke: none)
  rect((0, 510), (9, 595), fill: burgundy, stroke: none)
  content((38, 558), text(font: font-name, size: 21pt, weight: "bold", fill: white)[#figure-title], anchor: "west")
  content((39, 528), text(font: font-name, size: 10pt, fill: rgb("#D8E1EC"))[#subtitle], anchor: "west")
  rect((693, 535), (805, 568), radius: 17, fill: rgb("#243A56"), stroke: 0.8pt + rgb("#58708C"))
  content((749, 551.5), text(font: font-name, size: 8.5pt, weight: "bold", fill: white)[A4 横版], anchor: "center")

  content((42, 482), text(font: font-name, size: 9.5pt, weight: "bold", fill: burgundy)[#section-title], anchor: "west")
  line((42, 466), (800, 466), stroke: 0.8pt + line-color)
  line((252, 417), (308, 417), stroke: 1.6pt + burgundy, mark: (end: ">"))
  line((534, 417), (590, 417), stroke: 1.6pt + green, mark: (end: ">"))
  content((280, 437), text(font: font-name, size: 8pt, weight: "bold", fill: burgundy)[#comparison-1], anchor: "center")
  content((562, 437), text(font: font-name, size: 8pt, weight: "bold", fill: green)[#comparison-2], anchor: "center")

  card(42, 374, 210, 82, "__GROUP_A_TAG__", "__GROUP_A_TITLE__", "__GROUP_A_BODY_1__", rgb("#EAF3FA"), rgb("#9EBBD2"), blue)
  card(308, 374, 226, 82, "__GROUP_B_TAG__", "__GROUP_B_TITLE__", "__GROUP_B_BODY_1__", rgb("#FFF3E2"), rgb("#D9A86F"), amber)
  card(590, 374, 210, 82, "__GROUP_C_TAG__", "__GROUP_C_TITLE__", "__GROUP_C_BODY_1__", rgb("#EAF5EF"), rgb("#9DC5AF"), green)

  line((147, 374), (147, 355), stroke: 1.2pt + line-color)
  line((421, 374), (421, 347), stroke: 1.2pt + line-color)
  line((695, 374), (695, 355), stroke: 1.2pt + line-color)
  line((147, 355), (695, 355), stroke: 1.2pt + line-color)
  line((421, 355), (421, 342), stroke: 1.8pt + burgundy, mark: (end: ">"))

  rect((221, 272), (621, 342), radius: 13, fill: burgundy, stroke: 1.4pt + rgb("#6E1531"))
  content((421, 318), text(font: font-name, size: 9.5pt, weight: "bold", fill: rgb("#F7CBD9"))[#hub-label], anchor: "center")
  content((421, 295), text(font: font-name, size: 10.5pt, weight: "bold", fill: white)[#hub-combined], anchor: "center")
  content((421, 278), text(font: font-name, size: 7pt, fill: rgb("#F4DCE4"))[#hub-note], anchor: "center")

  line((421, 272), (421, 252), stroke: 1.8pt + burgundy)
  line((151, 252), (691, 252), stroke: 1.2pt + line-color)
  line((151, 252), (151, 230), stroke: 1.2pt + line-color, mark: (end: ">"))
  line((421, 252), (421, 230), stroke: 1.2pt + line-color, mark: (end: ">"))
  line((691, 252), (691, 230), stroke: 1.2pt + line-color, mark: (end: ">"))

  card(42, 125, 218, 105, "__MODULE_1_TAG__", "__MODULE_1_TITLE__", "__MODULE_1_BODY_1__", rgb("#EAF3FA"), rgb("#9EBBD2"), blue)
  card(312, 125, 218, 105, "__MODULE_2_TAG__", "__MODULE_2_TITLE__", "__MODULE_2_BODY_1__", rgb("#F7E9EE"), rgb("#D5A2B2"), burgundy)
  card(582, 125, 218, 105, "__MODULE_3_TAG__", "__MODULE_3_TITLE__", "__MODULE_3_BODY_1__", rgb("#EAF5EF"), rgb("#9DC5AF"), green)

  line((151, 125), (151, 108), stroke: 1.1pt + line-color)
  line((421, 125), (421, 101), stroke: 1.1pt + line-color)
  line((691, 125), (691, 108), stroke: 1.1pt + line-color)
  line((151, 108), (691, 108), stroke: 1.1pt + line-color)
  line((421, 108), (421, 95), stroke: 1.6pt + burgundy, mark: (end: ">"))
  rect((190, 48), (652, 95), radius: 10, fill: white, stroke: 1.1pt + line-color)
  content((421, 71.5), text(font: font-name, size: 9.5pt, weight: "bold", fill: ink)[#outcome], anchor: "center")
  content((800, 16), text(font: font-name, size: 7pt, fill: muted)[#footer], anchor: "east")
})
