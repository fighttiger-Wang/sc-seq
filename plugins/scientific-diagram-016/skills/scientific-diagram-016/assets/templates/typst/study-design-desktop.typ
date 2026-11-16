#import "@preview/cetz:0.3.4": canvas, draw

#let font-name = "__FONT__"
#let figure-title = "__TITLE__"
#let subtitle = "__SUBTITLE__"
#let badge = "__BADGE__"
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

#set page(width: 1440pt, height: 880pt, margin: 0pt, fill: white)
#set text(font: font-name, size: 12pt, fill: rgb("#172033"))

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
  let card(x, y, w, h, tag, title, body-1, body-2, fill-color, stroke-color, accent-color) = {
    rect((x, y), (x + w, y + h), radius: 16, fill: fill-color, stroke: 1.5pt + stroke-color)
    rect((x, y), (x + 8, y + h), radius: (left: 16, right: 0), fill: accent-color, stroke: none)
    content((x + 28, y + h - 22), text(font: font-name, size: 11pt, weight: "bold", fill: accent-color)[#tag], anchor: "north-west")
    content((x + 28, y + h - 52), text(font: font-name, size: 19pt, weight: "bold", fill: ink)[#title], anchor: "north-west")
    content((x + 28, y + 47), text(font: font-name, size: 11.5pt, fill: muted)[#body-1], anchor: "west")
    content((x + 28, y + 25), text(font: font-name, size: 11.5pt, fill: muted)[#body-2], anchor: "west")
  }

  rect((0, 0), (1440, 748), fill: rgb("#F5F7FA"), stroke: none)
  rect((0, 748), (1440, 880), fill: navy, stroke: none)
  rect((0, 748), (16, 880), fill: burgundy, stroke: none)
  content((72, 832), text(font: font-name, size: 30pt, weight: "bold", fill: white)[#figure-title], anchor: "west")
  content((74, 786), text(font: font-name, size: 14pt, fill: rgb("#D8E1EC"))[#subtitle], anchor: "west")
  rect((1162, 790), (1364, 838), radius: 24, fill: rgb("#243A56"), stroke: 1pt + rgb("#58708C"))
  content((1263, 814), text(font: font-name, size: 12pt, weight: "bold", fill: white)[#badge], anchor: "center")

  content((80, 704), text(font: font-name, size: 13pt, weight: "bold", fill: burgundy)[#section-title], anchor: "west")
  line((80, 682), (1360, 682), stroke: 1pt + line-color)
  line((440, 602), (548, 602), stroke: 2.2pt + burgundy, mark: (end: ">"))
  line((892, 602), (1000, 602), stroke: 2.2pt + green, mark: (end: ">"))
  content((494, 629), text(font: font-name, size: 11.5pt, weight: "bold", fill: burgundy)[#comparison-1], anchor: "center")
  content((946, 629), text(font: font-name, size: 11.5pt, weight: "bold", fill: green)[#comparison-2], anchor: "center")

  line((275, 530), (275, 500), stroke: 1.8pt + line-color)
  line((720, 530), (720, 482), stroke: 1.8pt + line-color)
  line((1165, 530), (1165, 500), stroke: 1.8pt + line-color)
  line((275, 500), (1165, 500), stroke: 1.8pt + line-color)
  line((720, 500), (720, 470), stroke: 2.4pt + burgundy, mark: (end: ">"))
  line((720, 374), (720, 344), stroke: 2.4pt + burgundy)
  line((285, 344), (1155, 344), stroke: 1.8pt + line-color)
  line((285, 344), (285, 314), stroke: 1.8pt + line-color, mark: (end: ">"))
  line((720, 344), (720, 314), stroke: 1.8pt + line-color, mark: (end: ">"))
  line((1155, 344), (1155, 314), stroke: 1.8pt + line-color, mark: (end: ">"))

  card(110, 530, 330, 136, "__GROUP_A_TAG__", "__GROUP_A_TITLE__", "__GROUP_A_BODY_1__", "__GROUP_A_BODY_2__", rgb("#EAF3FA"), rgb("#9EBBD2"), blue)
  card(555, 530, 330, 136, "__GROUP_B_TAG__", "__GROUP_B_TITLE__", "__GROUP_B_BODY_1__", "__GROUP_B_BODY_2__", rgb("#FFF3E2"), rgb("#D9A86F"), amber)
  card(1000, 530, 330, 136, "__GROUP_C_TAG__", "__GROUP_C_TITLE__", "__GROUP_C_BODY_1__", "__GROUP_C_BODY_2__", rgb("#EAF5EF"), rgb("#9DC5AF"), green)

  rect((402, 374), (1038, 470), radius: 20, fill: burgundy, stroke: 2pt + rgb("#6E1531"))
  content((720, 438), text(font: font-name, size: 14pt, weight: "bold", fill: rgb("#F7CBD9"))[#hub-label], anchor: "center")
  content((720, 407), text(font: font-name, size: 16.5pt, weight: "bold", fill: white)[#hub-combined], anchor: "center")
  content((720, 385), text(font: font-name, size: 9.5pt, fill: rgb("#F4DCE4"))[#hub-note], anchor: "center")

  card(110, 166, 350, 148, "__MODULE_1_TAG__", "__MODULE_1_TITLE__", "__MODULE_1_BODY_1__", "__MODULE_1_BODY_2__", rgb("#EAF3FA"), rgb("#9EBBD2"), blue)
  card(545, 166, 350, 148, "__MODULE_2_TAG__", "__MODULE_2_TITLE__", "__MODULE_2_BODY_1__", "__MODULE_2_BODY_2__", rgb("#F7E9EE"), rgb("#D5A2B2"), burgundy)
  card(980, 166, 350, 148, "__MODULE_3_TAG__", "__MODULE_3_TITLE__", "__MODULE_3_BODY_1__", "__MODULE_3_BODY_2__", rgb("#EAF5EF"), rgb("#9DC5AF"), green)

  line((285, 166), (285, 142), stroke: 1.5pt + line-color)
  line((720, 166), (720, 142), stroke: 1.5pt + line-color)
  line((1155, 166), (1155, 142), stroke: 1.5pt + line-color)
  line((285, 142), (1155, 142), stroke: 1.5pt + line-color)
  line((720, 142), (720, 124), stroke: 2pt + burgundy, mark: (end: ">"))
  rect((284, 56), (1156, 124), radius: 16, fill: white, stroke: 1.5pt + line-color)
  content((720, 92), text(font: font-name, size: 16pt, weight: "bold", fill: ink)[#outcome], anchor: "center")
  content((1358, 28), text(font: font-name, size: 10pt, fill: muted)[#footer], anchor: "east")
})
