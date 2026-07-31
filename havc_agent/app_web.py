"""Havc-Agent 企业控制台（Streamlit）。

设计语言：浅色企业标准（控制台 / 运维台），IBM Plex Sans + Noto Sans SC，
深蓝主色，无霓虹。运行：streamlit run havc_agent/app_web.py
"""
from __future__ import annotations

import time

import streamlit as st

from havc_agent.engine import Engine
from havc_agent.llm.provider import ping_llm, provider_status
from havc_agent.schemas import CabinContext, OccupantState, SceneInput
from havc_agent.sim import ClosedLoopSim

_GENDERS = ["male", "female"]
_EMOTIONS = ["neutral", "happy", "angry", "sad", "joy", "worried"]
_ACTIVITIES = ["excited", "calm", "sleeping"]
_CLOTHINGS = ["light", "medium", "heavy"]
_SEATS = ["driver", "front_passenger", "rear_left", "rear_right"]
_SEASONS = ["summer", "winter", "transition"]
_WEATHER = ["sunny", "cloudy", "rain", "snow"]
_RAIN = ["none", "light", "moderate", "heavy"]
_RAIN_ZH = {"none": "无雨", "light": "小雨", "moderate": "中雨", "heavy": "大雨"}
_DEFOG_ZH = {"none": "无需除雾", "mild": "轻度除雾", "strong": "强除雾"}
_SEAT_ZH = {
    "driver": "主驾", "front_passenger": "副驾",
    "rear_left": "左后", "rear_right": "右后",
}
_MODE_ZH = {
    "face": "吹面", "face_feet": "面+脚", "feet": "吹脚",
    "face_defrost": "吹面·除霜", "face_feet_defrost": "面脚·除霜",
    "feet_defrost": "吹脚·除霜", "defrost": "纯除霜",
}
_CAT_ZH = {"child": "小孩", "adult": "大人", "elderly": "老人"}
_ACT_ZH = {"sleeping": "睡眠", "calm": "平静", "excited": "兴奋"}
_ENERGY_ZH = {"normal": "正常", "save": "节能", "critical": "强节能"}


def _inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap');

:root{
  --bg:#F4F6F9; --panel:#FFFFFF; --line:#E2E8F0; --text:#1A202C;
  --muted:#64748B; --primary:#1E4D8C; --primary-soft:#E8F0FA;
  --ok:#0F766E; --warn:#B45309; --danger:#B91C1C;
}
html, body, [class*="css"]{
  font-family:'IBM Plex Sans','Noto Sans SC',sans-serif;
}
.stApp{ background:var(--bg); color:var(--text); }
section[data-testid="stSidebar"]{
  background:#FFFFFF; border-right:1px solid var(--line);
}
.topbar{
  background:var(--panel); border:1px solid var(--line); border-radius:8px;
  padding:16px 20px; margin-bottom:14px;
  display:flex; align-items:center; gap:16px; flex-wrap:wrap;
}
.brand{
  font-weight:700; font-size:20px; color:var(--primary); letter-spacing:.3px; margin:0;
}
.brand-sub{ color:var(--muted); font-size:13px; margin-top:2px; }
.tag{
  display:inline-block; font-size:12px; font-weight:500; padding:3px 10px;
  border-radius:4px; border:1px solid var(--line); background:#F8FAFC; color:var(--muted);
}
.tag.ok{ color:var(--ok); border-color:#99F6E4; background:#F0FDFA; }
.tag.warn{ color:var(--warn); border-color:#FDE68A; background:#FFFBEB; }
.tag.pri{ color:var(--primary); border-color:#BFDBFE; background:var(--primary-soft); }
.panel-title{
  font-size:15px; font-weight:600; color:var(--text); margin:0 0 8px 0;
  padding-bottom:8px; border-bottom:1px solid var(--line);
}
.kv{ font-size:13px; color:var(--muted); line-height:1.7; }
.kv b{ color:var(--text); font-weight:600; }
.chain-item{
  border-left:3px solid var(--primary); background:#F8FAFC;
  padding:8px 12px; margin:6px 0; border-radius:0 6px 6px 0; font-size:13px;
}
.chain-item.final{ border-left-color:var(--ok); background:#F0FDFA; }
.stButton>button{
  border-radius:6px; font-weight:600; border:1px solid var(--line);
}
.stTabs [data-baseweb="tab"]{ font-weight:600; }
[data-testid="stMetricValue"]{ color:var(--primary); font-weight:700; }
[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--panel); border:1px solid var(--line)!important; border-radius:8px;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _engine() -> Engine:
    if "engine" not in st.session_state:
        st.session_state.engine = Engine()
    return st.session_state.engine


def _topbar(scene: SceneInput, result) -> None:
    c = scene.cabin
    rid = getattr(result, "request_id", "") if result else ""
    tags = [
        f"<span class='tag'>季节 {c.season}</span>",
        f"<span class='tag'>外温 {c.ambient_temp:.0f}℃</span>",
        f"<span class='tag'>内温 {c.cabin_temp if c.cabin_temp is not None else '-'}℃</span>",
        f"<span class='tag'>SOC {c.soc:.0f}%</span>",
        f"<span class='tag'>湿度 {c.humidity:.0f}%</span>",
    ]
    if c.max_defrost:
        tags.append("<span class='tag warn'>MAX 除霜</span>")
    if rid:
        tags.append(f"<span class='tag pri'>RID {rid}</span>")
    st.markdown(
        f"""<div class="topbar">
        <div>
          <div class="brand">HAVC Agent Console</div>
          <div class="brand-sub">座舱热管理 Agent 集群 · 企业控制台</div>
        </div>
        <div style="flex:1"></div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">{''.join(tags)}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _sidebar_ops(eng: Engine) -> None:
    st.sidebar.markdown("### 系统接入")
    s = provider_status()
    st.sidebar.markdown(
        f"**Provider** `{s['provider']}`  \n"
        f"**Model** `{s['model']}`  \n"
        f"**状态** {s['mode']}"
    )
    if st.sidebar.button("测试 LLM 连接", width="stretch"):
        ok, msg = ping_llm()
        (st.sidebar.success if ok else st.sidebar.error)(msg)
    st.sidebar.caption("密钥配置见项目根目录 `.env`，修改后需重启。")
    st.sidebar.divider()

    st.sidebar.markdown("### Agent 集群")
    for a in eng.cluster.summary():
        flag = "启用" if a["enabled"] else "停用"
        st.sidebar.markdown(
            f"**{a['name']}** · P{a['priority']} · {flag}  \n"
            f"<span style='color:#64748B;font-size:12px'>{a['description']}</span>",
            unsafe_allow_html=True,
        )
    st.sidebar.caption("启停见 `config/agents.yaml`")
    st.sidebar.divider()


def _build_scene() -> SceneInput:
    st.sidebar.markdown("### 场景参数")
    season = st.sidebar.selectbox("季节", _SEASONS)
    weather = st.sidebar.selectbox("天气", _WEATHER)
    ambient = st.sidebar.slider("车外温度 ℃", -30.0, 50.0, 32.0)
    cabin_t = st.sidebar.slider("车内温度 ℃", -20.0, 80.0, 38.0)
    humidity = st.sidebar.slider("相对湿度 %", 0.0, 100.0, 55.0)
    sun_d = st.sidebar.slider("主驾日照 W/m²", 0.0, 1500.0, 900.0, 50.0)
    sun_p = st.sidebar.slider("副驾日照 W/m²", 0.0, 1500.0, 700.0, 50.0)
    soc = st.sidebar.slider("电量 %", 0.0, 100.0, 70.0)
    speed = st.sidebar.slider("车速 km/h", 0.0, 200.0, 0.0, 5.0)
    max_defrost = st.sidebar.checkbox("最大除霜 MAX", value=False)

    with st.sidebar.expander("除雾传感输入", expanded=False):
        rain_level = st.selectbox(
            "雨量", _RAIN, format_func=lambda x: _RAIN_ZH[x]
        )
        ws_air = st.slider("玻璃附近空气温度 ℃", -30.0, 60.0, float(cabin_t))
        ws_glass = st.slider("玻璃表面温度 ℃", -30.0, 60.0, float(ambient))

    st.sidebar.markdown("### 乘员")
    n = st.sidebar.slider("在座人数", 1, 4, 2)
    occupants, windows_open = [], {}
    for i in range(n):
        with st.sidebar.expander(f"座位 {i + 1}", expanded=i == 0):
            seat = st.selectbox("座位", _SEATS, index=min(i, 3), key=f"seat{i}")
            user = st.text_input(
                "用户", value=["alice", "bob", "carol", "dave"][i], key=f"user{i}"
            )
            age = st.slider("年龄", 1, 90, 35, key=f"age{i}")
            gender = st.selectbox("性别", _GENDERS, key=f"g{i}")
            height = st.slider("身高 cm", 80, 200, 170, key=f"h{i}")
            weight = st.slider("体重 kg", 10, 130, 65, key=f"w{i}")
            clothing = st.selectbox("衣着", _CLOTHINGS, index=1, key=f"cl{i}")
            emotion = st.selectbox("情绪", _EMOTIONS, key=f"em{i}")
            activity = st.selectbox("活动", _ACTIVITIES, index=1, key=f"ac{i}")
            win = st.slider("车窗 %", 0, 100, 0, key=f"win{i}")
            if win > 0:
                windows_open[seat] = float(win)
            occ = OccupantState(
                seat_id=seat, user_id=user, age=age, gender=gender,
                height_cm=float(height), weight_kg=float(weight),
                clothing=clothing, emotion=emotion, activity=activity,
            )
            st.caption(f"BMI {occ.bmi} · {_CAT_ZH[occ.category]}")
            occupants.append(occ)

    return SceneInput(
        cabin=CabinContext(
            ambient_temp=ambient, cabin_temp=cabin_t, weather=weather,
            humidity=humidity, sun_driver_wm2=sun_d, sun_passenger_wm2=sun_p,
            soc=soc, speed=speed, season=season,
            windshield_air_temp=ws_air, windshield_glass_temp=ws_glass,
            rain_level=rain_level, windows_open=windows_open,
            max_defrost=max_defrost, timestamp=time.time(),
        ),
        occupants=occupants,
    )


def _rebuild_scene(cabin_obj, occupants, cabin_update: dict | None = None) -> SceneInput:
    """用 dict 重建 SceneInput，避免 Streamlit 热重载后「旧 CabinContext 类 ≠ 新类」。"""
    data = cabin_obj.model_dump() if hasattr(cabin_obj, "model_dump") else dict(cabin_obj)
    if cabin_update:
        data.update(cabin_update)
    return SceneInput(
        cabin=CabinContext.model_validate(data),
        occupants=list(occupants),
    )


def _status_banners(scene: SceneInput, eng: Engine, result) -> None:
    d = eng.defog_for(scene.cabin) if eng.cluster.is_enabled("defog") else None
    if d is not None:
        if d.need_defog:
            st.warning(
                f"除雾 Agent：{_DEFOG_ZH[d.level]}（{d.source}）· "
                f"雨量 {_RAIN_ZH.get(scene.cabin.rain_level)} · {d.reasoning}"
            )
        else:
            st.info(f"除雾 Agent：{_DEFOG_ZH[d.level]}（{d.source}）· 不叠加除霜")

    energy = getattr(result, "energy", None)
    if energy is not None and energy.level != "normal":
        st.warning(
            f"能耗 Agent：{_ENERGY_ZH.get(energy.level, energy.level)} · "
            f"风量上限 {energy.fan_cap} · 偏置 {energy.temp_bias}℃ · "
            f"{'；'.join(energy.notes[:2])}"
        )

    pending = eng.pending.get(eng.vehicle_id)
    if pending:
        c1, c2, c3 = st.columns([4, 1, 1])
        c1.warning(f"待确认 · {pending.reason} · ticket `{pending.ticket_id}`")
        if c2.button("确认下发", width="stretch"):
            fb = eng.confirm_pending("confirm")
            st.success(fb.message if fb else "已确认")
            st.rerun()
        if c3.button("拒绝", width="stretch"):
            fb = eng.confirm_pending("reject")
            st.info(fb.message if fb else "已拒绝")
            st.rerun()

    fb = getattr(result, "feedback", None)
    if fb and fb.code.value == "DEGRADED":
        st.caption(f"回执：{fb.message}")


def _zone_table(result) -> None:
    rows = []
    for seat, s in result.settings.items():
        t = result.traces.get(seat)
        m = t.comfort_metrics if t else None
        rows.append({
            "座位": _SEAT_ZH.get(seat, seat),
            "设定℃": s.temp_set,
            "风量": s.fan_level,
            "出风": _MODE_ZH.get(s.air_mode, s.air_mode),
            "PMV": m.pmv if m else "-",
            "PPD%": m.ppd if m else "-",
            "目标℃": m.target_temp if m else "-",
            "来源": t.source if t else "-",
            "应用": "是" if result.applied.get(seat) else "维持",
        })
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)


def _sim_panel(sim: ClosedLoopSim | None) -> None:
    """闭环热仿真状态、热流与历史曲线。"""
    st.markdown('<div class="panel-title">闭环热仿真（舱温动力学）</div>', unsafe_allow_html=True)
    if sim is None:
        st.info(
            "点击侧栏「启动闭环热仿真」：按吸热/放热 + 空调送风每 10s 推进舱温，"
            "并重新推理设定，直至 |PMV|≤0.5 且 PPD≤10%。"
        )
        return

    stt = sim.status()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("仿真时刻", f"{stt['t_s']:.0f} s")
    c2.metric("舱内温度", f"{stt['cabin_temp']:.1f} ℃")
    c3.metric("本步 ΔT", f"{(stt['last_dT'] or 0):.2f} ℃")
    c4.metric("空调热流", f"{(stt['q_hvac_w'] or 0):.0f} W")
    c5.metric("日照得热", f"{(stt['q_solar_w'] or 0):.0f} W")

    if sim.converged:
        st.success(
            f"已收敛：全体乘员 |PMV|≤{sim.pmv_abs_limit} 且 PPD≤{sim.ppd_limit}% "
            f"（用时 {sim.t_s:.0f}s / {sim.step_i} 步）"
        )
    elif sim.running:
        st.warning("仿真运行中：每 10 秒自动更新舱温与 Agent 设定…")
    else:
        st.caption(f"已停止（步数 {sim.step_i}/{sim.max_steps}）。可重新启动。")

    if sim.last_thermal:
        th = sim.last_thermal.to_dict()
        st.caption(
            f"热平衡：Q_amb={th['q_amb_w']}W · Q_solar={th['q_solar_w']}W · "
            f"Q_vent={th['q_vent_w']}W · Q_hvac={th['q_hvac_w']}W · "
            f"送风 {th['t_supply']}℃ / {th['mass_flow']}kg/s"
        )

    if sim.history:
        chart_rows = []
        for snap in sim.history:
            avg_pmv = (
                sum(snap.pmv.values()) / len(snap.pmv) if snap.pmv else None
            )
            chart_rows.append({
                "t_s": snap.t_s,
                "舱温℃": snap.cabin_temp,
                "平均PMV": None if avg_pmv is None else round(avg_pmv, 2),
            })
        st.line_chart(chart_rows, x="t_s", y=["舱温℃", "平均PMV"])


def _sim_do_tick() -> bool:
    """推进一帧热仿真；成功返回 True。"""
    sim = st.session_state.get("sim")
    if sim is None or not sim.running:
        return False
    with st.spinner(f"仿真步进中 t={sim.t_s:.0f}s → {sim.t_s + sim.dt_s:.0f}s…"):
        result = sim.tick()
    st.session_state.result = result
    st.session_state.sim = sim
    st.session_state["_sim_last_tick_ts"] = time.time()
    return True


@st.fragment(run_every=10)
def _sim_auto_tick() -> None:
    """每 10 秒自动推进一帧（fragment 时钟）。

    注意：启动时只做了 t=0 推理，舱温要等 tick 才会下降。
    st.rerun() 后 fragment 会立刻重挂载，用时间戳避免连跳。
    """
    sim = st.session_state.get("sim")
    if sim is None or not sim.running:
        return
    cab = sim.scene.cabin.cabin_temp
    now = time.time()
    last = float(st.session_state.get("_sim_last_tick_ts", 0.0))
    remain = max(0, int(10 - (now - last)))
    st.caption(
        f"⏱ 仿真运行中 · t={sim.t_s:.0f}s · 舱温 {cab}℃ · "
        f"{'步进中…' if remain <= 0 else f'{remain}s 后下一步'}"
    )
    if now - last < 9.5:
        return
    if _sim_do_tick():
        st.rerun()


def _dashboard(scene: SceneInput, eng: Engine, result) -> None:
    sim = st.session_state.get("sim")
    _sim_panel(sim)
    _status_banners(scene, eng, result)
    st.markdown('<div class="panel-title">多温区设定总览</div>', unsafe_allow_html=True)
    _zone_table(result)

    st.markdown('<div class="panel-title">分区状态（只读 · Agent 闭环输出）</div>', unsafe_allow_html=True)
    if not result.settings:
        st.warning("暂无温区设定，请先推理或启动仿真。")
        return
    cols = st.columns(min(2, max(1, len(result.settings))))
    for i, (seat, s) in enumerate(result.settings.items()):
        t = result.traces[seat]
        occ = next((o for o in scene.occupants if o.seat_id == seat), None)
        with cols[i % len(cols)]:
            with st.container(border=True):
                title = f"**{_SEAT_ZH[seat]}** · {t.user_id}"
                if occ:
                    title += f" · {_CAT_ZH[occ.category]}/{occ.age}岁"
                st.markdown(title)
                m1, m2, m3 = st.columns(3)
                m1.metric("设定温度", f"{s.temp_set}℃")
                m2.metric("风量", f"{s.fan_level}/7")
                m3.metric("出风", _MODE_ZH.get(s.air_mode, s.air_mode))
                if t.comfort_metrics:
                    m = t.comfort_metrics
                    st.caption(
                        f"舱温感≈{m.cabin_temp}℃ · PMV {m.pmv} · PPD {m.ppd}% · "
                        f"舒适锚点 {m.target_temp}℃"
                    )
                if t.knowledge_snippets:
                    st.caption("知识：" + " | ".join(t.knowledge_snippets[:2]))
                for adj in t.safety_adjustments[:3]:
                    st.caption("护栏：" + adj)


def _chain_panel(scene: SceneInput, eng: Engine, result) -> None:
    st.markdown('<div class="panel-title">除雾 Agent 推理链</div>', unsafe_allow_html=True)
    if eng.cluster.is_enabled("defog"):
        for step in eng.stream_defog(scene.cabin):
            cls = "chain-item final" if step.node == "final" else "chain-item"
            st.markdown(
                f"<div class='{cls}'><b>{step.title}</b><br>{step.detail}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("除雾 Agent 已在配置中停用。")

    st.markdown('<div class="panel-title">舒适 Agent 推理链</div>', unsafe_allow_html=True)
    for seat, steps in (result.chains or {}).items():
        with st.expander(f"{_SEAT_ZH.get(seat, seat)} 推理步骤", expanded=True):
            for step in steps:
                cls = "chain-item final" if step.node == "final" else "chain-item"
                st.markdown(
                    f"<div class='{cls}'><b>{step.title}</b><br>{step.detail}</div>",
                    unsafe_allow_html=True,
                )


def _cluster_panel(eng: Engine, result) -> None:
    st.markdown('<div class="panel-title">集群与可观测性</div>', unsafe_allow_html=True)
    st.dataframe(eng.cluster.summary(), width="stretch", hide_index=True)
    st.markdown(
        f"<div class='kv'>车辆 ID：<b>{eng.vehicle_id}</b><br>"
        f"最近请求：<b>{getattr(result, 'request_id', '-')}</b><br>"
        f"入站合并：<b>{'是' if getattr(result, 'coalesced', False) else '否'}</b><br>"
        f"回执：<b>{getattr(getattr(result, 'feedback', None), 'message', '-')}</b></div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="HAVC Agent Console",
        layout="wide",
        page_icon="🌡️",
        initial_sidebar_state="expanded",
    )
    _inject_css()
    eng = _engine()
    _sidebar_ops(eng)
    scene = _build_scene()

    st.sidebar.markdown("### 闭环热仿真")
    st.sidebar.caption(
        "集总热容：环境导热 + 日照得热 + 开窗通风 + 空调送风。"
        "每 10s 更新舱温并重跑 Agent，直到乘客舒适。"
    )
    start_sim = st.sidebar.button("启动闭环热仿真", type="primary", width="stretch")
    stop_sim = st.sidebar.button("停止仿真", width="stretch")
    step_once = st.sidebar.button("单步推进 10s", width="stretch")

    if stop_sim and st.session_state.get("sim"):
        st.session_state.sim.running = False

    if start_sim:
        sim = ClosedLoopSim(engine=eng, scene=scene, dt_s=10.0, max_steps=60)
        with st.spinner("初始化闭环仿真（首次推理）…"):
            result0 = sim.start(initial_infer=True)
        # 立刻热步进一帧：否则界面会一直停在侧栏内温（如 38℃），像“没反应”
        if sim.running:
            with st.spinner("推进热模型 10s…"):
                result0 = sim.tick()
        st.session_state.sim = sim
        st.session_state.result = result0
        st.session_state["_sim_last_tick_ts"] = time.time()

    if step_once and st.session_state.get("sim"):
        sim = st.session_state.sim
        if not sim.running and not sim.converged:
            sim.running = True
        if sim.running:
            _sim_do_tick()

    run = st.sidebar.button("仅执行推理（无热步进）", width="stretch")
    auto = st.sidebar.checkbox("参数变更后自动推理", value=False)

    sim = st.session_state.get("sim")
    # 侧栏「车内温度」滑条只作初始条件；仿真启动后以热模型舱温为准，不再被滑条覆盖
    if sim is not None and (sim.running or sim.history):
        try:
            display_scene = _rebuild_scene(
                sim.scene.cabin,
                scene.occupants,
                {
                    "ambient_temp": scene.cabin.ambient_temp,
                    "sun_driver_wm2": scene.cabin.sun_driver_wm2,
                    "sun_passenger_wm2": scene.cabin.sun_passenger_wm2,
                    "speed": scene.cabin.speed,
                    "humidity": scene.cabin.humidity,
                    "soc": scene.cabin.soc,
                    "weather": scene.cabin.weather,
                    "season": scene.cabin.season,
                    "windows_open": scene.cabin.windows_open,
                    "max_defrost": scene.cabin.max_defrost,
                    "rain_level": scene.cabin.rain_level,
                    "windshield_air_temp": scene.cabin.windshield_air_temp,
                    "windshield_glass_temp": scene.cabin.windshield_glass_temp,
                },
            )
            sim.scene = display_scene
        except Exception:
            # 热重载导致 session 里旧 sim 与新类不兼容：清掉，让用户重新启动
            st.session_state.pop("sim", None)
            st.session_state.pop("result", None)
            st.warning("检测到代码热更新，已重置仿真状态，请重新点击「启动闭环热仿真」。")
            display_scene = scene
            sim = None
        if sim is not None:
            st.sidebar.info(
                f"仿真舱温 **{display_scene.cabin.cabin_temp}℃** "
                f"(t={sim.t_s:.0f}s，侧栏内温滑条仅作启动初值)"
            )
    else:
        display_scene = scene

    if run or (auto and "result" not in st.session_state) or "result" not in st.session_state:
        with st.spinner("Agent 集群推理中…"):
            st.session_state.result = eng.infer(
                display_scene, capture_chain=True, force=True
            )

    result = st.session_state.result
    _topbar(display_scene, result)

    # 自动时钟放在侧栏，便于看到「还在跑」
    with st.sidebar:
        _sim_auto_tick()

    tab1, tab2, tab3 = st.tabs(["运行总览", "推理链路", "集群运维"])
    with tab1:
        _dashboard(display_scene, eng, result)
    with tab2:
        _chain_panel(display_scene, eng, result)
    with tab3:
        _cluster_panel(eng, result)


if __name__ == "__main__":
    main()
