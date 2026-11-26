/* global THREE */

/* ======================= CONSTANTS ======================= */
const FIELD_W = 64;          // x width
const FIELD_L = 100;         // z length
const HALF_W = FIELD_W / 2;
const HALF_L = FIELD_L / 2;
const GOAL_HALF_WIDTH = 7;
const GOAL_HEIGHT = 5;
const GOAL_LINE_Z = HALF_L;  // opponent goal at +HALF_L, your goal at -HALF_L

const MATCH_SECONDS = 180;

const TEAM_YOU = "you";
const TEAM_RIVAL = "rival";

const COLORS = {
  youJersey: 0xd93b3b,
  youShorts: 0x1b1b1b,
  rivalJersey: 0x2f5fd9,
  rivalShorts: 0xffffff,
  gkYou: 0xf2c53d,
  gkRival: 0x3ddc73,
  skin: 0xe2b084,
};

/* ======================= RENDERER / SCENE ======================= */
const canvas = document.getElementById("gameCanvas");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x8fcBe8);
scene.fog = new THREE.Fog(0x8fcbe8, 70, 140);

const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 300);

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
resize();

/* ======================= LIGHTS ======================= */
scene.add(new THREE.HemisphereLight(0xffffff, 0x3a5a2a, 0.75));
const sun = new THREE.DirectionalLight(0xffffff, 1.05);
sun.position.set(30, 50, -20);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
sun.shadow.camera.left = -60;
sun.shadow.camera.right = 60;
sun.shadow.camera.top = 60;
sun.shadow.camera.bottom = -60;
sun.shadow.camera.far = 150;
scene.add(sun);

/* ======================= FIELD ======================= */
function buildPitchTexture() {
  const cw = 1024, ch = Math.round(cw * (FIELD_L / FIELD_W));
  const cv = document.createElement("canvas");
  cv.width = cw; cv.height = ch;
  const ctx = cv.getContext("2d");

  // mowed stripes
  const stripes = 12;
  for (let i = 0; i < stripes; i++) {
    ctx.fillStyle = i % 2 === 0 ? "#3f9a3f" : "#379237";
    ctx.fillRect(0, (ch / stripes) * i, cw, ch / stripes);
  }

  const toPxX = (x) => (x / FIELD_W + 0.5) * cw;
  const toPxY = (z) => (z / FIELD_L + 0.5) * ch;

  ctx.strokeStyle = "rgba(255,255,255,0.9)";
  ctx.lineWidth = 4;

  // outer boundary
  ctx.strokeRect(toPxX(-HALF_W) + 2, toPxY(-HALF_L) + 2, toPxX(HALF_W) - toPxX(-HALF_W) - 4, toPxY(HALF_L) - toPxY(-HALF_L) - 4);
  // halfway line
  ctx.beginPath();
  ctx.moveTo(toPxX(-HALF_W), toPxY(0));
  ctx.lineTo(toPxX(HALF_W), toPxY(0));
  ctx.stroke();
  // center circle
  ctx.beginPath();
  ctx.arc(toPxX(0), toPxY(0), toPxX(9) - toPxX(0), 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(toPxX(0), toPxY(0), 5, 0, Math.PI * 2);
  ctx.fillStyle = "white";
  ctx.fill();

  // penalty boxes + goal boxes (both ends)
  [-1, 1].forEach((side) => {
    const boxZ = side * HALF_L;
    const dir = -side; // box extends inward
    ctx.strokeRect(toPxX(-16), toPxY(boxZ), toPxX(16) - toPxX(-16), toPxY(boxZ + dir * 18) - toPxY(boxZ));
    ctx.strokeRect(toPxX(-9), toPxY(boxZ), toPxX(9) - toPxX(-9), toPxY(boxZ + dir * 7) - toPxY(boxZ));
    ctx.beginPath();
    ctx.arc(toPxX(0), toPxY(boxZ + dir * 11), toPxX(9) - toPxX(0), 0, Math.PI * 2);
    ctx.stroke();
  });

  const tex = new THREE.CanvasTexture(cv);
  tex.anisotropy = 4;
  return tex;
}

const pitchGeo = new THREE.PlaneGeometry(FIELD_W, FIELD_L);
const pitchMat = new THREE.MeshStandardMaterial({ map: buildPitchTexture(), roughness: 1 });
const pitch = new THREE.Mesh(pitchGeo, pitchMat);
pitch.rotation.x = -Math.PI / 2;
pitch.receiveShadow = true;
scene.add(pitch);

// surrounding ground (so the world doesn't end abruptly)
const groundMat = new THREE.MeshStandardMaterial({ color: 0x2f7a35, roughness: 1 });
const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), groundMat);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.02;
ground.receiveShadow = true;
scene.add(ground);

function buildGoal(z) {
  const group = new THREE.Group();
  const postMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.4 });
  const postGeo = new THREE.CylinderGeometry(0.14, 0.14, GOAL_HEIGHT, 8);

  const leftPost = new THREE.Mesh(postGeo, postMat);
  leftPost.position.set(-GOAL_HALF_WIDTH, GOAL_HEIGHT / 2, 0);
  const rightPost = leftPost.clone();
  rightPost.position.x = GOAL_HALF_WIDTH;

  const barGeo = new THREE.CylinderGeometry(0.14, 0.14, GOAL_HALF_WIDTH * 2, 8);
  const bar = new THREE.Mesh(barGeo, postMat);
  bar.rotation.z = Math.PI / 2;
  bar.position.set(0, GOAL_HEIGHT, 0);

  // back support posts
  const backDepth = 2.6;
  const backL = leftPost.clone(); backL.position.z = -backDepth * Math.sign(z || 1);
  const backR = rightPost.clone(); backR.position.z = -backDepth * Math.sign(z || 1);

  const net = new THREE.Mesh(
    new THREE.PlaneGeometry(GOAL_HALF_WIDTH * 2, GOAL_HEIGHT),
    new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.22, side: THREE.DoubleSide, wireframe: true })
  );
  net.position.set(0, GOAL_HEIGHT / 2, -backDepth * Math.sign(z || 1));

  [leftPost, rightPost, bar, backL, backR].forEach((m) => { m.castShadow = true; group.add(m); });
  group.add(net);
  group.position.z = z;
  if (z < 0) group.rotation.y = Math.PI;
  scene.add(group);
}
buildGoal(-GOAL_LINE_Z);
buildGoal(GOAL_LINE_Z);

/* ======================= BALL ======================= */
function buildBallTexture() {
  const s = 256;
  const cv = document.createElement("canvas");
  cv.width = s; cv.height = s;
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#f4f4f4";
  ctx.fillRect(0, 0, s, s);
  ctx.fillStyle = "#1a1a1a";
  for (let i = 0; i < 6; i++) {
    for (let j = 0; j < 6; j++) {
      if ((i + j) % 2 === 0) ctx.fillRect(i * (s / 6), j * (s / 6), s / 6, s / 6);
    }
  }
  return new THREE.CanvasTexture(cv);
}
const BALL_RADIUS = 0.33;
const ballMesh = new THREE.Mesh(
  new THREE.SphereGeometry(BALL_RADIUS, 20, 20),
  new THREE.MeshStandardMaterial({ map: buildBallTexture(), roughness: 0.5 })
);
ballMesh.castShadow = true;
scene.add(ballMesh);

const ball = {
  mesh: ballMesh,
  pos: new THREE.Vector3(0, BALL_RADIUS, 0),
  vel: new THREE.Vector3(0, 0, 0),
  owner: null,
};

/* ======================= HUMANOID PLAYER MESH ======================= */
function capsule(radius, length, color) {
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.75 });
  const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(radius, length, 4, 8), mat);
  mesh.castShadow = true;
  return mesh;
}

function buildHumanoid(jerseyColor, shortsColor, numberStr) {
  const root = new THREE.Group();

  // legs
  const legGroupL = new THREE.Group();
  legGroupL.position.set(-0.14, 1.0, 0);
  const legL = capsule(0.11, 0.62, COLORS.skin);
  legL.position.y = -0.37;
  legGroupL.add(legL);
  const shoeL = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.1, 0.32), new THREE.MeshStandardMaterial({ color: 0x111111 }));
  shoeL.position.set(0, -0.72, 0.06);
  shoeL.castShadow = true;
  legGroupL.add(shoeL);

  const legGroupR = legGroupL.clone(true);
  legGroupR.position.x = 0.14;

  // hips / shorts
  const hips = capsule(0.28, 0.1, shortsColor);
  hips.position.y = 1.0;

  // torso
  const torso = capsule(0.26, 0.5, jerseyColor);
  torso.position.y = 1.35;

  // head
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 16), new THREE.MeshStandardMaterial({ color: COLORS.skin, roughness: 0.8 }));
  head.position.y = 1.78;
  head.castShadow = true;

  // hair
  const hair = new THREE.Mesh(new THREE.SphereGeometry(0.225, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0x241a12 }));
  hair.position.y = 1.80;
  head.add(hair);

  // arms
  const armGroupL = new THREE.Group();
  armGroupL.position.set(-0.36, 1.55, 0);
  const armL = capsule(0.085, 0.42, jerseyColor);
  armL.position.y = -0.22;
  const foreArmL = capsule(0.075, 0.2, COLORS.skin);
  foreArmL.position.y = -0.5;
  armGroupL.add(armL, foreArmL);

  const armGroupR = armGroupL.clone(true);
  armGroupR.position.x = 0.36;

  root.add(legGroupL, legGroupR, hips, torso, head, armGroupL, armGroupR);

  return { root, legGroupL, legGroupR, armGroupL, armGroupR, head };
}

/* ======================= PLAYER ENTITY ======================= */
class PlayerEntity {
  constructor({ team, role, isGK, isControlled, jersey, shorts }) {
    this.team = team;
    this.role = role; // 'gk' | 'def' | 'fwd'
    this.isGK = !!isGK;
    this.isControlled = !!isControlled;

    const parts = buildHumanoid(jersey, shorts);
    this.parts = parts;
    this.mesh = parts.root;
    scene.add(this.mesh);

    this.pos = new THREE.Vector3();
    this.home = new THREE.Vector3();
    this.facing = team === TEAM_YOU ? 0 : Math.PI; // radians, 0 = +z
    this.animPhase = Math.random() * 10;
    this.speed = 0;
    this.baseSpeed = isGK ? 4.5 : role === "fwd" ? 7.2 : 6.6;
    this.sprintMul = 1.0;

    if (this.isControlled) {
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.42, 0.52, 24),
        new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide, transparent: true, opacity: 0.85 })
      );
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.02;
      this.marker = ring;
      this.mesh.add(ring);
    }
  }

  setPosition(x, z) {
    this.pos.set(x, 0, z);
    this.mesh.position.set(x, 0, z);
  }

  update(dt, moveDir, isSprinting) {
    // moveDir: THREE.Vector3 (x,z) desired direction, normalized or zero
    const speed = this.baseSpeed * (isSprinting ? 1.55 : 1.0);
    this.speed = moveDir.length();

    if (this.speed > 0.01) {
      const targetAngle = Math.atan2(moveDir.x, moveDir.z);
      let diff = targetAngle - this.facing;
      diff = Math.atan2(Math.sin(diff), Math.cos(diff));
      this.facing += diff * Math.min(1, dt * 10);

      this.pos.x += moveDir.x * speed * dt;
      this.pos.z += moveDir.z * speed * dt;
    }

    this.pos.x = THREE.MathUtils.clamp(this.pos.x, -HALF_W + 0.5, HALF_W - 0.5);
    this.pos.z = THREE.MathUtils.clamp(this.pos.z, -HALF_L + 0.5, HALF_L - 0.5);

    this.mesh.position.set(this.pos.x, 0, this.pos.z);
    this.mesh.rotation.y = this.facing;

    // running animation
    const animSpeed = this.speed > 0.01 ? 9 : 4;
    this.animPhase += dt * animSpeed * (this.speed > 0.01 ? 1 : 0.0);
    const amp = this.speed > 0.01 ? 0.65 : 0;
    this.parts.legGroupL.rotation.x = Math.sin(this.animPhase) * amp;
    this.parts.legGroupR.rotation.x = Math.sin(this.animPhase + Math.PI) * amp;
    this.parts.armGroupL.rotation.x = Math.sin(this.animPhase + Math.PI) * amp * 0.75;
    this.parts.armGroupR.rotation.x = Math.sin(this.animPhase) * amp * 0.75;
  }
}

/* ======================= TEAM SETUP ======================= */
function makeFormation(team) {
  // positions expressed with "forward" meaning increasing |z| away from own goal
  const dir = team === TEAM_YOU ? 1 : -1;
  const ownGoalZ = team === TEAM_YOU ? -HALF_L : HALF_L;
  const list = [
    { role: "gk", x: 0, z: ownGoalZ + dir * 3 },
    { role: "def", x: -9, z: ownGoalZ + dir * 16 },
    { role: "def", x: 9, z: ownGoalZ + dir * 16 },
    { role: "fwd", x: -7, z: ownGoalZ + dir * 36 },
    { role: "fwd", x: 7, z: ownGoalZ + dir * 36 },
  ];
  return list;
}

const youFormation = makeFormation(TEAM_YOU);
const rivalFormation = makeFormation(TEAM_RIVAL);

const youPlayers = youFormation.map((f, i) =>
  new PlayerEntity({
    team: TEAM_YOU,
    role: f.role,
    isGK: f.role === "gk",
    isControlled: i === 3, // one of the forwards
    jersey: f.role === "gk" ? COLORS.gkYou : COLORS.youJersey,
    shorts: COLORS.youShorts,
  })
);
const rivalPlayers = rivalFormation.map((f) =>
  new PlayerEntity({
    team: TEAM_RIVAL,
    role: f.role,
    isGK: f.role === "gk",
    isControlled: false,
    jersey: f.role === "gk" ? COLORS.gkRival : COLORS.rivalJersey,
    shorts: COLORS.rivalShorts,
  })
);

const controlled = youPlayers.find((p) => p.isControlled);
const allPlayers = [...youPlayers, ...rivalPlayers];

function resetFormation() {
  youFormation.forEach((f, i) => youPlayers[i].setPosition(f.x, f.z));
  rivalFormation.forEach((f, i) => rivalPlayers[i].setPosition(f.x, f.z));
  ball.pos.set(0, BALL_RADIUS, 0);
  ball.vel.set(0, 0, 0);
  ball.owner = null;
}
resetFormation();

/* ======================= STATE ======================= */
const state = {
  score: { you: 0, rival: 0 },
  timeLeft: MATCH_SECONDS,
  running: false,
  paused: false,
  stamina: 1,
  sprintHeld: false,
};

/* ======================= INPUT: JOYSTICK ======================= */
const joyBase = document.getElementById("joystickBase");
const joyStick = document.getElementById("joystickStick");
const moveVec = { x: 0, y: 0 }; // y here = screen-vertical axis (up = +)
let joyActive = false;
let joyPointerId = null;
const JOY_MAX = 36;

function joyRect() { return joyBase.getBoundingClientRect(); }

function setJoy(dx, dy) {
  const len = Math.hypot(dx, dy);
  const clamped = Math.min(len, JOY_MAX);
  const ang = Math.atan2(dy, dx);
  const cx = Math.cos(ang) * clamped;
  const cy = Math.sin(ang) * clamped;
  joyStick.style.transform = `translate(${cx}px, ${cy}px)`;
  moveVec.x = clamped > 4 ? (cx / JOY_MAX) : 0;
  moveVec.y = clamped > 4 ? (-cy / JOY_MAX) : 0; // invert so up = positive
}

function joyReset() {
  joyStick.style.transform = `translate(0px,0px)`;
  moveVec.x = 0; moveVec.y = 0;
}

joyBase.addEventListener("pointerdown", (e) => {
  joyActive = true;
  joyPointerId = e.pointerId;
  joyBase.setPointerCapture(e.pointerId);
  const r = joyRect();
  setJoy(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
});
joyBase.addEventListener("pointermove", (e) => {
  if (!joyActive || e.pointerId !== joyPointerId) return;
  const r = joyRect();
  setJoy(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
});
function joyEnd(e) {
  if (e.pointerId !== joyPointerId) return;
  joyActive = false;
  joyReset();
}
joyBase.addEventListener("pointerup", joyEnd);
joyBase.addEventListener("pointercancel", joyEnd);

/* Keyboard fallback for desktop testing */
const keys = {};
window.addEventListener("keydown", (e) => { keys[e.key.toLowerCase()] = true; });
window.addEventListener("keyup", (e) => { keys[e.key.toLowerCase()] = false; });

function getKeyboardVec() {
  let x = 0, y = 0;
  if (keys["arrowleft"] || keys["a"]) x -= 1;
  if (keys["arrowright"] || keys["d"]) x += 1;
  if (keys["arrowup"] || keys["w"]) y += 1;
  if (keys["arrowdown"] || keys["s"]) y -= 1;
  return { x, y };
}

/* ======================= INPUT: ACTION BUTTONS ======================= */
const btnA = document.getElementById("btnA");
const btnB = document.getElementById("btnB");
const btnC = document.getElementById("btnC");

btnA.addEventListener("pointerdown", (e) => { e.preventDefault(); doPass(); });
btnB.addEventListener("pointerdown", (e) => { e.preventDefault(); doShoot(); });
btnC.addEventListener("pointerdown", (e) => { e.preventDefault(); state.sprintHeld = true; });
btnC.addEventListener("pointerup", () => { state.sprintHeld = false; });
btnC.addEventListener("pointercancel", () => { state.sprintHeld = false; });
window.addEventListener("keydown", (e) => {
  if (e.key.toLowerCase() === "j") doPass();
  if (e.key.toLowerCase() === "k") doShoot();
  if (e.key === "Shift") state.sprintHeld = true;
});
window.addEventListener("keyup", (e) => { if (e.key === "Shift") state.sprintHeld = false; });

/* ======================= GAME ACTIONS ======================= */
function youHaveBall() {
  return ball.owner && ball.owner.team === TEAM_YOU;
}

function doPass() {
  if (ball.owner !== controlled) return;
  // find best open teammate ahead of controlled player
  const candidates = youPlayers.filter((p) => p !== controlled);
  let best = null, bestScore = -Infinity;
  candidates.forEach((p) => {
    const forwardness = p.pos.z - controlled.pos.z; // positive = further toward rival goal
    const lateral = Math.abs(p.pos.x - controlled.pos.x);
    const score = forwardness * 1.4 - lateral * 0.5;
    if (score > bestScore) { bestScore = score; best = p; }
  });
  if (!best) return;
  kickBallTowards(best.pos, 15, 1.2);
  ball.owner = null;
}

function doShoot() {
  if (ball.owner !== controlled) return;
  const targetX = THREE.MathUtils.clamp(-controlled.pos.x * 0.3 + (Math.random() - 0.5) * 4, -GOAL_HALF_WIDTH + 1, GOAL_HALF_WIDTH - 1);
  const target = new THREE.Vector3(targetX, 0, HALF_L);
  kickBallTowards(target, 26, 7.5);
  ball.owner = null;
}

function kickBallTowards(targetPos, speed, liftVel) {
  const dir = new THREE.Vector3(targetPos.x - ball.pos.x, 0, targetPos.z - ball.pos.z).normalize();
  ball.vel.set(dir.x * speed, liftVel, dir.z * speed);
}

/* ======================= AI ======================= */
const PICKUP_RADIUS = 1.1;

function aiMoveDir(player) {
  const dir = new THREE.Vector3();
  if (player.isGK) {
    const ownGoalZ = player.team === TEAM_YOU ? -HALF_L : HALF_L;
    const targetX = THREE.MathUtils.clamp(ball.pos.x, -GOAL_HALF_WIDTH + 1, GOAL_HALF_WIDTH - 1);
    const targetZ = ownGoalZ + (player.team === TEAM_YOU ? 1 : -1) * 2.5;
    dir.set(targetX - player.pos.x, 0, targetZ - player.pos.z);
    // come out a bit if ball is very close to goal
    const distBallToGoal = Math.abs(ball.pos.z - ownGoalZ);
    if (distBallToGoal < 14 && Math.abs(ball.pos.x) < GOAL_HALF_WIDTH + 3) {
      dir.set(ball.pos.x - player.pos.x, 0, ball.pos.z - player.pos.z);
    }
    return dir.lengthSq() > 0.0004 ? dir.normalize() : dir;
  }

  const myTeamHasBall = ball.owner && ball.owner.team === player.team;
  const rivalTeamHasBall = ball.owner && ball.owner.team !== player.team;
  const attackDir = player.team === TEAM_YOU ? 1 : -1;

  if (myTeamHasBall) {
    // make a forward run into space, keep some width, don't overlap the ball owner
    const spread = player.home.x * 0.6 + (player.role === "fwd" ? attackDir * 10 : attackDir * 2);
    const targetX = THREE.MathUtils.clamp(spread, -HALF_W + 4, HALF_W - 4);
    const targetZ = ball.owner.pos.z + attackDir * (player.role === "fwd" ? 10 : 4);
    dir.set(targetX - player.pos.x, 0, targetZ - player.pos.z);
  } else if (rivalTeamHasBall) {
    // press the ball if within range depending on role, else fall back toward home
    const distToBall = player.pos.distanceTo(new THREE.Vector3(ball.pos.x, 0, ball.pos.z));
    const pressRange = player.role === "fwd" ? 22 : 30;
    if (distToBall < pressRange) {
      dir.set(ball.pos.x - player.pos.x, 0, ball.pos.z - player.pos.z);
    } else {
      dir.set(player.home.x - player.pos.x, 0, player.home.z - player.pos.z);
    }
  } else {
    // loose ball: whoever is reasonably close chases it, others hold shape
    const distToBall = player.pos.distanceTo(new THREE.Vector3(ball.pos.x, 0, ball.pos.z));
    if (distToBall < 16) {
      dir.set(ball.pos.x - player.pos.x, 0, ball.pos.z - player.pos.z);
    } else {
      dir.set(player.home.x - player.pos.x, 0, player.home.z - player.pos.z);
    }
  }
  return dir.lengthSq() > 0.0004 ? dir.normalize() : dir;
}

// store home positions for fallback shape-holding
youFormation.forEach((f, i) => youPlayers[i].home.set(f.x, 0, f.z));
rivalFormation.forEach((f, i) => rivalPlayers[i].home.set(f.x, 0, f.z));

// simple AI for rival team controlling their own "controlled-equivalent": none needed,
// rival ball carrier also uses aiMoveDir plus shoot/pass heuristics handled below.

function aiBallCarrierDecision(player) {
  const attackGoalZ = player.team === TEAM_YOU ? HALF_L : -HALF_L;
  const distToGoal = Math.abs(attackGoalZ - player.pos.z);
  if (distToGoal < 24 && Math.random() < 0.03) {
    const target = new THREE.Vector3(THREE.MathUtils.clamp(-player.pos.x * 0.2, -GOAL_HALF_WIDTH + 1, GOAL_HALF_WIDTH - 1), 0, attackGoalZ);
    kickBallTowards(target, 24, 6.5);
    ball.owner = null;
    return;
  }
  if (Math.random() < 0.015) {
    const teammates = (player.team === TEAM_YOU ? youPlayers : rivalPlayers).filter((p) => p !== player);
    const attackDir = player.team === TEAM_YOU ? 1 : -1;
    let best = null, bestScore = -Infinity;
    teammates.forEach((p) => {
      const forwardness = (p.pos.z - player.pos.z) * attackDir;
      const score = forwardness - Math.abs(p.pos.x - player.pos.x) * 0.4;
      if (score > bestScore) { bestScore = score; best = p; }
    });
    if (best) { kickBallTowards(best.pos, 14, 1.0); ball.owner = null; }
  }
}

/* ======================= BALL PHYSICS ======================= */
const GRAVITY = -16;
function updateBall(dt) {
  if (ball.owner) {
    const o = ball.owner;
    const offset = 0.75;
    ball.pos.x = o.pos.x + Math.sin(o.facing) * offset;
    ball.pos.z = o.pos.z + Math.cos(o.facing) * offset;
    ball.pos.y = BALL_RADIUS;
    ball.vel.set(0, 0, 0);
  } else {
    ball.vel.y += GRAVITY * dt;
    ball.pos.x += ball.vel.x * dt;
    ball.pos.y += ball.vel.y * dt;
    ball.pos.z += ball.vel.z * dt;

    if (ball.pos.y <= BALL_RADIUS) {
      ball.pos.y = BALL_RADIUS;
      if (ball.vel.y < 0) ball.vel.y *= -0.35;
      if (Math.abs(ball.vel.y) < 0.6) ball.vel.y = 0;
      const friction = Math.max(0, 1 - dt * 1.2);
      ball.vel.x *= friction;
      ball.vel.z *= friction;
    }

    // side/back wall bounce (keep ball roughly on pitch area)
    if (ball.pos.x < -HALF_W + BALL_RADIUS || ball.pos.x > HALF_W - BALL_RADIUS) {
      ball.vel.x *= -0.5;
      ball.pos.x = THREE.MathUtils.clamp(ball.pos.x, -HALF_W + BALL_RADIUS, HALF_W - BALL_RADIUS);
    }
  }

  ball.mesh.position.copy(ball.pos);

  // pickup check
  if (!ball.owner) {
    let nearest = null, nearestDist = PICKUP_RADIUS;
    allPlayers.forEach((p) => {
      const d = p.pos.distanceTo(new THREE.Vector3(ball.pos.x, 0, ball.pos.z));
      if (d < nearestDist) { nearestDist = d; nearest = p; }
    });
    if (nearest && ball.pos.y < 1.2) {
      ball.owner = nearest;
      ball.vel.set(0, 0, 0);
    }
  } else {
    // owner can lose the ball if another player gets closer (simple contest)
    const ownerDist = ball.owner.pos.distanceTo(new THREE.Vector3(ball.pos.x, 0, ball.pos.z));
    allPlayers.forEach((p) => {
      if (p === ball.owner) return;
      const d = p.pos.distanceTo(ball.owner.pos);
      if (d < 0.55 && Math.random() < 0.02) {
        ball.owner = p;
      }
    });
  }

  checkGoal();
}

function checkGoal() {
  if (ball.pos.z > GOAL_LINE_Z + BALL_RADIUS * 0.5 && Math.abs(ball.pos.x) < GOAL_HALF_WIDTH && ball.pos.y < GOAL_HEIGHT) {
    scoreGoal(TEAM_YOU);
  } else if (ball.pos.z < -GOAL_LINE_Z - BALL_RADIUS * 0.5 && Math.abs(ball.pos.x) < GOAL_HALF_WIDTH && ball.pos.y < GOAL_HEIGHT) {
    scoreGoal(TEAM_RIVAL);
  }
}

/* ======================= SCORE / FLOW ======================= */
const scoreEl = document.getElementById("score");
const timerEl = document.getElementById("timer");
const goalFlashEl = document.getElementById("goalFlash");

function scoreGoal(team) {
  if (state.paused) return;
  state.score[team]++;
  scoreEl.textContent = `${state.score.you} : ${state.score.rival}`;
  goalFlashEl.classList.remove("show");
  void goalFlashEl.offsetWidth;
  goalFlashEl.classList.add("show");
  playGoalSound();

  state.paused = true;
  setTimeout(() => {
    resetFormation();
    state.paused = false;
  }, 1800);
}

/* simple synthesized goal sound, no external asset needed */
let audioCtx = null;
function playGoalSound() {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const now = audioCtx.currentTime;
    [0, 0.12, 0.24].forEach((t, i) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "square";
      osc.frequency.value = 520 + i * 180;
      gain.gain.value = 0.08;
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(now + t);
      gain.gain.exponentialRampToValueAtTime(0.001, now + t + 0.2);
      osc.stop(now + t + 0.22);
    });
  } catch (e) { /* audio unavailable, ignore */ }
}

function formatTime(sec) {
  const m = Math.floor(sec / 60).toString().padStart(2, "0");
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

/* ======================= CAMERA ======================= */
const camOffset = new THREE.Vector3(0, 13, -15);
const camTarget = new THREE.Vector3();
function updateCamera(dt) {
  const desired = new THREE.Vector3(controlled.pos.x * 0.6, 0, controlled.pos.z).add(camOffset);
  camera.position.lerp(desired, Math.min(1, dt * 3));
  camTarget.lerp(new THREE.Vector3(controlled.pos.x * 0.3, 1, controlled.pos.z + 6), Math.min(1, dt * 3));
  camera.lookAt(camTarget);
}

/* ======================= MAIN LOOP ======================= */
const clock = new THREE.Clock();

function tick() {
  requestAnimationFrame(tick);
  const dt = Math.min(clock.getDelta(), 0.05);

  if (state.running && !state.paused) {
    // controlled player input
    const kb = getKeyboardVec();
    const inX = moveVec.x !== 0 || moveVec.y !== 0 ? moveVec.x : kb.x;
    const inY = moveVec.x !== 0 || moveVec.y !== 0 ? moveVec.y : kb.y;
    const moveDir = new THREE.Vector3(inX, 0, inY);
    if (moveDir.lengthSq() > 1) moveDir.normalize();

    const isSprinting = state.sprintHeld && state.stamina > 0.03 && moveDir.lengthSq() > 0.01;
    if (isSprinting) state.stamina = Math.max(0, state.stamina - dt * 0.35);
    else state.stamina = Math.min(1, state.stamina + dt * 0.18);
    document.getElementById("staminaBar").style.width = `${state.stamina * 100}%`;

    controlled.update(dt, moveDir, isSprinting);

    // AI players
    allPlayers.forEach((p) => {
      if (p === controlled) return;
      const dir = aiMoveDir(p);
      p.update(dt, dir, false);
    });

    // rival (and any AI) ball-carrier decisions
    if (ball.owner && ball.owner !== controlled) {
      aiBallCarrierDecision(ball.owner);
    }

    updateBall(dt);
    updateCamera(dt);

    state.timeLeft -= dt;
    if (state.timeLeft <= 0) {
      state.timeLeft = 0;
      endMatch();
    }
    timerEl.textContent = formatTime(state.timeLeft);
  }

  renderer.render(scene, camera);
}
tick();

/* ======================= START / END SCREENS ======================= */
const startScreen = document.getElementById("startScreen");
const endScreen = document.getElementById("endScreen");
const startBtn = document.getElementById("startBtn");
const restartBtn = document.getElementById("restartBtn");
const finalScoreEl = document.getElementById("finalScore");

startBtn.addEventListener("click", () => {
  startScreen.classList.add("hidden");
  state.running = true;
});

function endMatch() {
  state.running = false;
  finalScoreEl.textContent = `SIZ ${state.score.you} : ${state.score.rival} RAQIB — ${
    state.score.you > state.score.rival ? "SIZ G'ALABA QOZONDINGIZ!" :
    state.score.you < state.score.rival ? "MAG'LUBIYAT" : "DURANG"
  }`;
  endScreen.classList.remove("hidden");
}

restartBtn.addEventListener("click", () => {
  state.score.you = 0;
  state.score.rival = 0;
  state.timeLeft = MATCH_SECONDS;
  state.stamina = 1;
  scoreEl.textContent = "0 : 0";
  timerEl.textContent = formatTime(state.timeLeft);
  resetFormation();
  endScreen.classList.add("hidden");
  state.running = true;
});
