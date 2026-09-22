import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = process.cwd();
const SKILL_DIR = process.env.PRESENTATIONS_SKILL_DIR;
const RUNTIME_PYTHON = process.env.RUNTIME_PYTHON;
const TMP_DIR = process.env.ROLELENS_SLIDE_TMP_DIR
  ?? path.join(workspaceDir, "tmp", "presentations", "rolelens-slides");
const FINAL_PPTX = process.env.ROLELENS_SLIDE_PPTX
  ?? path.join(workspaceDir, "output", "pptx", "RoleLens_서비스보고서_슬라이드.pptx");

if (!SKILL_DIR || !path.isAbsolute(SKILL_DIR)) {
  throw new Error("PRESENTATIONS_SKILL_DIR must be an absolute path");
}
if (!RUNTIME_PYTHON || !path.isAbsolute(RUNTIME_PYTHON)) {
  throw new Error("RUNTIME_PYTHON must be an absolute path");
}

const { finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);

await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });

const W = 1280;
const H = 720;
const FONT = "Nanum Gothic";
const C = {
  paper: "#F7F4EE",
  white: "#FFFFFF",
  ink: "#18222D",
  muted: "#68737D",
  rule: "#D9D6CF",
  accent: "#E56F45",
  accentTint: "#FBE8DF",
  link: "#3A6EA5",
  positive: "#2E7D64",
};

const presentation = Presentation.create({ slideSize: { width: W, height: H } });

function addText(slide, text, x, y, w, h, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: FONT,
    fontSize: opts.fontSize ?? 24,
    bold: opts.bold ?? false,
    color: opts.color ?? C.ink,
    alignment: opts.alignment ?? "left",
    verticalAlignment: opts.verticalAlignment ?? "top",
    autoFit: opts.autoFit ?? "shrinkText",
    wrap: "square",
    insets: opts.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
  };
  return shape;
}

function addRect(slide, x, y, w, h, fill, opts = {}) {
  return slide.shapes.add({
    geometry: opts.geometry ?? "rect",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: opts.line ?? { fill: "none", width: 0 },
    ...(opts.borderRadius ? { borderRadius: opts.borderRadius } : {}),
    ...(opts.shadow ? { shadow: opts.shadow } : {}),
  });
}

function addRule(slide, x, y, w, color = C.rule, height = 2) {
  return addRect(slide, x, y, w, height, color);
}

async function addImage(slide, relPath, position, opts = {}) {
  const absPath = path.join(workspaceDir, relPath);
  const blob = await fs.readFile(absPath);
  const ext = path.extname(absPath).toLowerCase();
  const contentType = ext === ".svg" ? "image/svg+xml" : "image/png";
  return slide.images.add({
    blob,
    contentType,
    alt: opts.alt ?? path.basename(absPath),
    fit: opts.fit ?? "contain",
    position,
    ...(opts.crop ? { crop: opts.crop } : {}),
    ...(opts.geometry ? { geometry: opts.geometry } : {}),
    ...(opts.borderRadius ? { borderRadius: opts.borderRadius } : {}),
  });
}

function baseSlide(index, section, title) {
  const slide = presentation.slides.add();
  slide.background.fill = C.paper;
  addRule(slide, 64, 34, 1152, C.rule, 2);
  addText(slide, section, 64, 48, 720, 22, {
    fontSize: 13,
    bold: true,
    color: C.accent,
  });
  addText(slide, title, 64, 78, 1110, 62, {
    fontSize: 44,
    bold: true,
  });
  addText(slide, "RoleLens", 64, 684, 160, 18, { fontSize: 12, color: C.muted });
  addText(slide, String(index).padStart(2, "0"), 1170, 684, 46, 18, {
    fontSize: 12,
    color: C.muted,
    alignment: "right",
  });
  return slide;
}

function addMetric(slide, x, y, w, value, label, accent = C.ink) {
  addRule(slide, x, y, w, accent, 5);
  addText(slide, value, x, y + 18, w, 54, { fontSize: 42, bold: true, color: accent });
  addText(slide, label, x, y + 74, w, 40, { fontSize: 17, color: C.muted });
}

// 1. Cover
{
  const slide = presentation.slides.add();
  slide.background.fill = C.paper;
  addRect(slide, 0, 0, 18, H, C.accent);
  addText(slide, "LANGCHAIN  POSTGRESQL  GRADIO", 80, 66, 560, 24, {
    fontSize: 14,
    bold: true,
    color: C.accent,
  });
  addText(slide, "RoleLens", 80, 150, 620, 92, { fontSize: 76, bold: true });
  addText(slide, "직무 관점형 자연어 데이터 분석 도우미", 84, 260, 760, 48, {
    fontSize: 34,
    color: C.ink,
  });
  addRule(slide, 82, 338, 170, C.accent, 6);
  addText(slide, "핵심 구조와 실제 실행 결과", 84, 365, 540, 42, {
    fontSize: 24,
    color: C.muted,
  });
  addText(slide, "SEED 42 MOCK DATA", 84, 562, 290, 26, {
    fontSize: 16,
    bold: true,
    color: C.accent,
  });
  addText(slide, "데이터 기준일  2026-09-15", 84, 605, 330, 24, { fontSize: 17, color: C.muted });
  addText(slide, "2026-09-22", 1010, 605, 190, 24, {
    fontSize: 17,
    color: C.muted,
    alignment: "right",
  });
  slide.speakerNotes.textFrame.setText("Source: README.md; docs/01_PROJECT_PROPOSAL.md; docs/02_PRD.md");
}

// 2. Product summary
{
  const slide = baseSlide(2, "PRODUCT", "SQL 작성과 해석을 하나의 흐름으로 연결");
  addText(slide, "데이터를 사용하지만 SQL이 본업은 아닌 사용자가 질문부터 Insight Card까지 바로 얻는다.", 64, 150, 1040, 40, {
    fontSize: 23,
    color: C.muted,
  });

  const personas = [
    { x: 64, name: "기획자", desc: "KPI 현재값\n목표 대비 격차", color: C.ink },
    { x: 448, name: "마케터", desc: "고객 세그먼트\n채널·매출 비교", color: C.accent },
    { x: 832, name: "PM", desc: "활성화율\n퍼널·기기별 차이", color: C.link },
  ];
  for (const p of personas) {
    addRule(slide, p.x, 224, 320, p.color, 5);
    addText(slide, p.name, p.x, 250, 320, 48, { fontSize: 34, bold: true, color: p.color });
    addText(slide, p.desc, p.x, 312, 320, 80, { fontSize: 22, color: C.muted });
  }

  const steps = [
    ["01", "질문 해석", "지표·기간·필터"],
    ["02", "SQL 실행", "읽기 전용 경계"],
    ["03", "수치 계산", "Python 결정론 로직"],
    ["04", "Insight Card", "핵심 답·차트·근거"],
  ];
  steps.forEach((s, i) => {
    const x = 64 + i * 288;
    addText(slide, s[0], x, 464, 60, 32, { fontSize: 17, bold: true, color: i === 3 ? C.accent : C.muted });
    addText(slide, s[1], x, 506, 250, 34, { fontSize: 25, bold: true, color: i === 3 ? C.accent : C.ink });
    addText(slide, s[2], x, 552, 250, 28, { fontSize: 17, color: C.muted });
  });
  slide.speakerNotes.textFrame.setText("Source: README.md; docs/02_PRD.md; src/rolelens");
}

// 3. Architecture and safety
{
  const slide = baseSlide(3, "SYSTEM", "처리 구조와 SQL 안전 경계");
  addRect(slide, 54, 144, 882, 482, C.white, { line: { style: "solid", fill: C.rule, width: 1 } });
  await addImage(slide, "reports/assets/diagrams/analysis-flow.png", {
    left: 68, top: 158, width: 854, height: 454,
  }, { alt: "RoleLens 질문부터 Insight Card까지의 처리 흐름" });

  addMetric(slide, 976, 158, 240, "6", "analytics 허용 테이블", C.ink);
  addMetric(slide, 976, 302, 240, "100", "최대 반환 행", C.accent);
  addMetric(slide, 976, 446, 240, "10s", "statement timeout", C.link);
  addText(slide, "AST 검사  ·  allowlist  ·  read-only DB role", 976, 590, 250, 36, {
    fontSize: 17,
    bold: true,
    color: C.positive,
  });
  slide.speakerNotes.textFrame.setText("Source: docs/03_TECHNICAL_DESIGN.md; src/rolelens/services/insight_service.py; src/rolelens/db/safety.py");
}

// 4. Marketer execution
{
  const slide = baseSlide(4, "EXECUTION", "마케터 시나리오 실제 실행");
  addText(slide, "“최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.”", 64, 150, 420, 92, {
    fontSize: 25,
    bold: true,
  });
  addRule(slide, 64, 270, 350, C.accent, 6);
  addText(slide, "9.22M", 64, 292, 350, 58, { fontSize: 49, bold: true, color: C.accent });
  addText(slide, "beauty 현재 3개월 매출  KRW", 64, 354, 350, 28, { fontSize: 17, color: C.muted });
  addText(slide, "+1,729.51%", 64, 414, 350, 54, { fontSize: 38, bold: true });
  addText(slide, "직전 3개월 대비", 64, 470, 350, 28, { fontSize: 17, color: C.muted });
  addText(slide, "completed 주문  ·  20 ≤ age < 30\nusers + orders + products", 64, 540, 370, 52, {
    fontSize: 17,
    color: C.muted,
  });

  addRect(slide, 500, 150, 716, 476, C.white, {
    line: { style: "solid", fill: C.rule, width: 1 },
    shadow: "shadow-sm",
  });
  await addImage(slide, "reports/assets/screenshots/02-marketer-result.png", {
    left: 510, top: 160, width: 696, height: 456,
  }, { alt: "Gradio 마케터 시나리오 실행 화면", fit: "contain" });
  addText(slide, "실제 PostgreSQL + reference SQL을 사용한 결정론적 인수 모드 캡처", 500, 638, 716, 24, {
    fontSize: 14,
    color: C.muted,
  });
  slide.speakerNotes.textFrame.setText("Source: reports/evidence/scenario-marketer.json; reports/assets/screenshots/02-marketer-result.png");
}

// 5. Three verified scenarios
{
  const slide = baseSlide(5, "RESULTS", "3개 직무 시나리오 검증 결과");
  const cols = [64, 448, 832];
  const blocks = [
    { x: cols[0], role: "기획자", metric: "95.69%", desc: "Q3 매출 목표 달성률", image: "reports/assets/charts/planner.png", color: C.ink },
    { x: cols[1], role: "마케터", metric: "9.22M", desc: "20대 beauty 최근 3개월 매출", image: "reports/assets/charts/marketer.png", color: C.accent },
    { x: cols[2], role: "PM", metric: "43.06%", desc: "mobile 7일 활성화율", image: "reports/assets/charts/pm.png", color: C.link },
  ];
  for (const b of blocks) {
    addRule(slide, b.x, 160, 320, b.color, 5);
    addText(slide, b.role, b.x, 183, 320, 34, { fontSize: 23, bold: true, color: b.color });
    addText(slide, b.metric, b.x, 226, 320, 58, { fontSize: 46, bold: true });
    addText(slide, b.desc, b.x, 289, 320, 46, { fontSize: 17, color: C.muted });
    addRect(slide, b.x, 358, 320, 190, C.white, { line: { style: "solid", fill: C.rule, width: 1 } });
    await addImage(slide, b.image, { left: b.x + 8, top: 366, width: 304, height: 174 }, {
      alt: `${b.role} 검증 차트`,
      fit: "contain",
    });
  }
  addText(slide, "Q3 실제 86,189,441.91원 / 목표 90,067,966.80원", 64, 580, 360, 40, { fontSize: 16, color: C.muted });
  addText(slide, "beauty 매출 9,224,188.55원", 448, 580, 320, 40, { fontSize: 16, color: C.muted });
  addText(slide, "desktop 61.70%  ·  tablet 66.67%", 832, 580, 320, 40, { fontSize: 16, color: C.muted });
  slide.speakerNotes.textFrame.setText("Source: sql/reference/ts01_planner_target.sql; ts02_marketer_twenty_category.sql; ts03_pm_activation.sql; reports/evidence/scenario-*.json");
}

// 6. Persona and clarification
{
  const slide = baseSlide(6, "BEHAVIOR", "페르소나 분기와 확인 질문");
  addText(slide, "같은 질문의 추가 차원은 직무에 따라 달라진다.", 64, 150, 560, 34, {
    fontSize: 22,
    color: C.muted,
  });
  addRect(slide, 64, 206, 610, 352, C.white, { line: { style: "solid", fill: C.rule, width: 1 } });
  await addImage(slide, "reports/assets/screenshots/04-persona-comparison.png", {
    left: 74, top: 216, width: 590, height: 332,
  }, { alt: "기획자와 마케터 결과 비교", fit: "contain" });
  addText(slide, "신규 고객: 기획자는 목표 격차, 마케터는 유입 채널을 우선", 64, 578, 610, 46, {
    fontSize: 17,
    bold: true,
  });

  addRect(slide, 714, 206, 502, 352, C.white, { line: { style: "solid", fill: C.accent, width: 2 } });
  await addImage(slide, "reports/assets/screenshots/05-clarification.png", {
    left: 724, top: 216, width: 482, height: 332,
  }, { alt: "모호한 질문에 대한 Gradio 확인 질문", fit: "contain" });
  addText(slide, "“최근 30일의 매출액을 기준으로 상위 상품을 보여드릴까요?”", 714, 578, 502, 46, {
    fontSize: 17,
    bold: true,
    color: C.accent,
  });
  addText(slide, "모호함을 해소할 때까지 SQL tool 호출 0회", 714, 630, 502, 24, {
    fontSize: 15,
    color: C.muted,
  });
  slide.speakerNotes.textFrame.setText("Source: reports/evidence/scenario-persona-comparison.json; reports/evidence/scenario-ambiguous.json");
}

// 7. Verification
{
  const slide = baseSlide(7, "VERIFICATION", "코드와 실행 결과 검증");
  addMetric(slide, 64, 166, 320, "76 / 76", "pytest 통과  ·  13.71초", C.accent);
  addMetric(slide, 448, 166, 320, "3 / 3", "기준 SQL 결과 일치", C.ink);
  addMetric(slide, 832, 166, 320, "100%", "검증한 위험 SQL 차단 / 제한", C.positive);

  addRule(slide, 64, 344, 544, C.rule, 2);
  addText(slide, "실행 환경", 64, 370, 250, 34, { fontSize: 24, bold: true });
  addText(slide, "PostgreSQL 16.15  ·  migration 20260921_0001\nusers 1,200  ·  orders 3,907  ·  events 5,203\nLIMIT 100  ·  statement timeout 10,000ms", 64, 422, 520, 110, {
    fontSize: 20,
    color: C.muted,
  });

  addRule(slide, 672, 344, 544, C.rule, 2);
  addText(slide, "Live LLM smoke", 672, 370, 320, 34, { fontSize: 24, bold: true });
  addText(slide, "gpt-4o-mini 마케터 질문 성공\n2회 수정 후 reference SQL fallback\n모호한 질문은 clarification 반환", 672, 422, 500, 110, {
    fontSize: 20,
    color: C.muted,
  });

  addRect(slide, 64, 570, 1152, 68, C.accentTint, { line: { fill: "none", width: 0 } });
  addText(slide, "UI 캡처: 결정론적 인수 모드    Live smoke: 실제 모델 호출", 88, 588, 1104, 32, {
    fontSize: 19,
    bold: true,
    color: C.ink,
  });
  slide.speakerNotes.textFrame.setText("Source: reports/evidence/test-summary.txt; environment-summary.txt; sql-safety-summary.txt; live-model-summary.json");
}

const requirements = {
  explicitTotalSlideCount: 7,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
};
const fontPolicy = {
  basis: "design",
  families: [FONT],
};
const expectedSlideSizeEmu = "12192000,6858000";
const stagingDir = path.join(TMP_DIR, ".codex-finalizer");
await fs.mkdir(stagingDir, { recursive: true });
const candidatePath = path.join(stagingDir, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const result = await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", expectedSlideSizeEmu,
    "--validate-heading-fit",
  ],
  requiredNativeTableOwnerSlides: [],
  fontPolicy,
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, `RoleLens_서비스보고서_슬라이드-${Date.now()}.validation.json`),
});

console.log(JSON.stringify({ final: FINAL_PPTX, result }, null, 2));
