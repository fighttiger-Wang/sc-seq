#import "@preview/cetz:0.3.4": canvas, draw

#let font-name = "__FONT__"
#let figure-title = "__MOBILE_TITLE__"
#let subtitle = "__SUBTITLE__"
#let section-title = "__SECTION_TITLE__"
#let comparison-1 = "__COMPARISON_1__"
#let comparison-2 = "__COMPARISON_2__"
#let hub-label = "__HUB_LABEL__"
#let hub-line-1 = "__HUB_LINE_1__"
#let hub-line-2 = "__HUB_LINE_2__"
#let hub-note = "__HUB_NOTE__"
#let module-section = "__MODULE_SECTION__"
#let outcome = "__OUTCOME__"
#let footer = "__FOOTER__"

#set page(width: 390pt, height: 1300pt, margin: 0pt, fill: white)
#set text(font: font-name, size: 13pt, fill: rgb("#172033"))

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
  let group-card(y, tag, title, body, fill-color, stroke-color, accent-color) = {
    rect((30, y), (360, y + 110), radius: 14, fill: fill-color, stroke: 1.4pt + stroke-color)
    rect((30, y), (37, y + 110), radius: (left: 14, right: 0), fill: accent-color, stroke: none)
    content((52, y + 84), text(font: font-name, size: 11.5pt, weight: "bold", fill: accent-color)[#tag], anchor: "west")
    content((52, y + 52), text(font: font-name, size: 18pt, weight: "bold", fill: ink)[#title], anchor: "west")
    content((52, y + 24), text(font: font-name, size: 12pt, fill: muted)[#body], anchor: "west")
  }
  let analysis-row(y, number, title, body, fill-color, accent-color) = {
    rect((48, y), (342, y + 68), radius: 12, fill: fill-color, stroke: 1pt + line-color)
    circle((76, y + 34), radius: 18, fill: accent-color, stroke: none)
    content((76, y + 34), text(font: font-name, size: 12pt, weight: "bold", fill: white)[#number], anchor: "center")
    content((106, y + 44), text(font: font-name, size: 13.5pt, weight: "bold", fill: ink)[#title], anchor: "west")
    content((106, y + 22), text(font: font-name, size: 10pt, fill: muted)[#body], anchor: "west")
  }

  rect((0, 0), (390, 1160), fill: rgb("#F5F7FA"), stroke: none)
  rect((0, 1160), (390, 1300), fill: navy, stroke: none)
  rect((0, 1160), (8, 1300), fill: burgundy, stroke: none)
  content((24, 1250), text(font: font-name, size: 21pt, weight: "bold", fill: white)[#figure-title], anchor: "west")
  content((24, 1207), text(font: font-name, size: 10.5pt, fill: rgb("#D8E1EC"))[#subtitle], anchor: "west")
  content((30, 1120), text(font: font-name, size: 13pt, weight: "bold", fill: burgundy)[#section-title], anchor: "west")
  line((30, 1099), (360, 1099), stroke: 1pt + line-color)

  group-card(980, "__GROUP_A_TAG__", "__GROUP_A_TITLE__", "__GROUP_A_BODY_1__", rgb("#EAF3FA"), rgb("#9EBBD2"), blue)
  group-card(820, "__GROUP_B_TAG__", "__GROUP_B_TITLE__", "__GROUP_B_BODY_1__", rgb("#FFF3E2"), rgb("#D9A86F"), amber)
  group-card(660, "__GROUP_C_TAG__", "__GROUP_C_TITLE__", "__GROUP_C_BODY_1__", rgb("#EAF5EF"), rgb("#9DC5AF"), green)

  line((195, 980), (195, 938), stroke: 2pt + burgundy, mark: (end: ">"))
  content((212, 959), text(font: font-name, size: 10.5pt, weight: "bold", fill: burgundy)[#comparison-1], anchor: "west")
  line((195, 820), (195, 778), stroke: 2pt + green, mark: (end: ">"))
  content((212, 799), text(font: font-name, size: 10.5pt, weight: "bold", fill: green)[#comparison-2], anchor: "west")
  line((195, 660), (195, 628), stroke: 2pt + burgundy, mark: (end: ">"))

  rect((30, 510), (360, 628), radius: 16, fill: burgundy, stroke: 1.8pt + rgb("#6E1531"))
  content((195, 598), text(font: font-name, size: 13pt, weight: "bold", fill: rgb("#F7CBD9"))[#hub-label], anchor: "center")
  content((195, 565), text(font: font-name, size: 13.5pt, weight: "bold", fill: white)[#hub-line-1], anchor: "center")
  content((195, 536), text(font: font-name, size: 13.5pt, weight: "bold", fill: white)[#hub-line-2], anchor: "center")
  content((195, 518), text(font: font-name, size: 9pt, fill: rgb("#F4DCE4"))[#hub-note], anchor: "center")

  line((195, 510), (195, 480), stroke: 2pt + burgundy, mark: (end: ">"))
  rect((30, 145), (360, 470), radius: 16, fill: white, stroke: 1.4pt + line-color)
  content((52, 443), text(font: font-name, size: 14pt, weight: "bold", fill: burgundy)[#module-section], anchor: "west")
  analysis-row(350, "01", "__MODULE_1_TITLE__", "__MODULE_1_BODY_1__", rgb("#EAF3FA"), blue)
  analysis-row(265, "02", "__MODULE_2_TITLE__", "__MODULE_2_BODY_1__", rgb("#F7E9EE"), burgundy)
  analysis-row(180, "03", "__MODULE_3_TITLE__", "__MODULE_3_BODY_1__", rgb("#EAF5EF"), green)

  line((195, 145), (195, 125), stroke: 2pt + burgundy, mark: (end: ">"))
  rect((30, 68), (360, 125), radius: 14, fill: white, stroke: 1.4pt + line-color)
  content((195, 97), text(font: font-name, size: 11.5pt, weight: "bold", fill: ink)[#outcome], anchor: "center")
  content((360, 24), text(font: font-name, size: 9pt, fill: muted)[#footer], anchor: "east")
})
