import io, os, numpy as np, pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ─── 한글 폰트 CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
   font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# ─── 열 이름 표준화 ─────────────────────────────────────────────────────────────
def std_cols(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif k == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"
    df = df.rename(columns=rename)
    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(
                df[c].astype(str).str.replace(",", "")
                .str.extract(r"(-?\d+\.?\d*)")[0], errors="coerce")
            if num.notna().mean() >= 0.5:
                df[c] = num
    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]
    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = pd.to_datetime(parts[0], format="%Y%m%d") + \
                          pd.to_timedelta(parts[1].astype(int), unit="h")
        df["time"] = parsed
    return df


def read_csv(file):
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()


def get_school_name(filename):
    return os.path.basename(filename).replace(".csv", "").strip()


# ─── 추세선 helper ─────────────────────────────────────────────────────────────
def add_trendline(fig, x, y, color="red", dash="dash"):
    valid = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(valid) < 2:
        return
    slope, intercept = np.polyfit(valid["x"], valid["y"], 1)
    xs = np.array([valid["x"].min(), valid["x"].max()])
    fig.add_trace(go.Scatter(
        x=xs, y=slope * xs + intercept,
        mode="lines", line=dict(color=color, dash=dash, width=1.5),
        name=f"추세선 (y={slope:.2f}x+{intercept:.2f})",
        hoverinfo="skip"
    ))


def scatter_with_r(fig, x_title, y_title, x, y, color="#1f77b4"):
    valid = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(valid) >= 2:
        r = valid["x"].corr(valid["y"])
    else:
        r = float("nan")
    fig.add_trace(go.Scatter(
        x=valid["x"], y=valid["y"],
        mode="markers", marker=dict(size=7, color=color, opacity=0.8),
        name=f"r = {r:.3f}" if not np.isnan(r) else "r = N/A",
        hovertemplate=(
            f"{x_title}: %{{x:.2f}}<br>{y_title}: %{{y:.2f}}"
            "<extra></extra>"
        )
    ))
    add_trendline(fig, valid["x"], valid["y"])
    fig.update_layout(
        xaxis_title=x_title,
        yaxis_title=y_title,
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
        legend=dict(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
    )
    return r


def base_layout(fig, title):
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=14, family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")
        ),
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig


# ─── 페이지 설정 & 제목 ─────────────────────────────────────────────────────────
st.set_page_config(page_title="극지식물 생육 분석", layout="wide")
st.title("🌱 우리 학교 극지식물 개체별 생육 차이 분석")

# ─── 사이드바: 파일 업로드 ───────────────────────────────────────────────────────
st.sidebar.header("📁 데이터 업로드")
env_file   = st.sidebar.file_uploader("환경 데이터 CSV", type="csv")
growth_file = st.sidebar.file_uploader("생육 결과 데이터 CSV", type="csv")

env_df       = pd.DataFrame()
growth_df    = pd.DataFrame()
school_name  = "예시 학교"

if env_file:
    env_df      = std_cols(read_csv(env_file))
    school_name = get_school_name(env_file.name)

if growth_file:
    growth_df    = std_cols(read_csv(growth_file))
    if school_name == "예시 학교":
        school_name = get_school_name(growth_file.name)

# ─── 데이터 없을 때 안내 ────────────────────────────────────────────────────────
if env_df.empty and growth_df.empty:
    st.info("📁 사이드바에서 환경 데이터 CSV와 생육 결과 CSV를 업로드해 주세요.")
    st.stop()

# ─── 탭 생성 ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 1 — 📖 실험 개요
# ══════════════════════════════════════════════════════════════════════════════════
with tab1:
    try:
        st.subheader(f"🏫 {school_name} 극지식물 생육 실험 개요")

        st.markdown("""
**연구 배경 및 목적**

극지식물은 열악한 환경에서도 생존하는 독특한 적응 전략을 가진 식물로,
개체마다 생육 상태와 환경 적응도에 차이가 나타난다는 관측이 있습니다.

이 대시보드에서는 우리 학교에서 재배 중인 극지식물 개체를 대상으로
**개체별 생중량 분포와 차이**, 잎 수·지상부 길이와 생중량의 **상관관계**,
그리고 **생중량 상위 25% vs 하위 25% 개체 비교**를 통해
개체 간 생육 차이를 정량적으로 분석합니다.
""")

        # 데이터 요약 표
        n_growth   = len(growth_df)   if not growth_df.empty   else 0
        n_env      = len(env_df)      if not env_df.empty      else 0
        env_has_time   = "time"      in env_df.columns and not env_df.empty
        growth_has_bio = "생중량"    in growth_df.columns  and not growth_df.empty

        summary_rows = []
        summary_rows.append(("개체 수", f"{n_growth}개"))
        if env_has_time:
            summary_rows.append(
                ("측정 기간",
                 f"{env_df['time'].min().strftime('%Y-%m-%d')} ~ "
                 f"{env_df['time'].max().strftime('%Y-%m-%d')}")
            )
        else:
            summary_rows.append(("측정 기간", "업로드 필요"))

        env_cols_present = [c for c in ["temperature", "humidity", "ph", "ec"]
                            if c in env_df.columns]
        if env_cols_present:
            label_map = {"temperature": "온도", "humidity": "습도",
                         "ph": "pH", "ec": "EC"}
            summary_rows.append(
                ("환경 측정 항목",
                 ", ".join(label_map[c] for c in env_cols_present))
            )
        else:
            summary_rows.append(("환경 측정 항목", "업로드 필요"))

        growth_cols = [c for c in ["생중량", "잎 수", "지상부 길이", "지하부 길이"]
                       if c in growth_df.columns]
        if growth_cols:
            g_label = {"생중량": "생중량", "잎 수": "잎 수",
                       "지상부 길이": "지상부 길이", "지하부 길이": "지하부 길이"}
            summary_rows.append(
                ("생육 측정 항목",
                 ", ".join(g_label[c] for c in growth_cols))
            )
        else:
            summary_rows.append(("생육 측정 항목", "업로드 필요"))

        st.markdown("#### 📋 데이터 요약")
        st.table(pd.DataFrame(summary_rows, columns=["항목", "내용"]))

        # 주요 지표 카드 4개
        col1, col2, col3, col4 = st.columns(4)

        avg_temp   = (env_df["temperature"].dropna().mean()
                      if "temperature" in env_df.columns and not env_df.empty else None)
        avg_humid  = (env_df["humidity"].dropna().mean()
                      if "humidity" in env_df.columns and not env_df.empty else None)
        avg_bio    = (growth_df["생중량"].dropna().mean()
                      if "생중량" in growth_df.columns and not growth_df.empty else None)

        with col1:
            st.metric("총 개체수", f"{n_growth}개" if n_growth > 0 else "업로드 필요")
        with col2:
            if avg_temp is not None and not pd.isna(avg_temp):
                st.metric("평균 온도", f"{avg_temp:.1f}℃")
            else:
                st.metric("평균 온도", "업로드 필요")
        with col3:
            if avg_humid is not None and not pd.isna(avg_humid):
                st.metric("평균 습도", f"{avg_humid:.1f}%")
            else:
                st.metric("평균 습도", "업로드 필요")
        with col4:
            if avg_bio is not None and not pd.isna(avg_bio):
                st.metric("평균 생중량", f"{avg_bio:.2f} g")
            else:
                st.metric("평균 생중량", "업로드 필요")

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 2 — 🌡️ 환경 데이터
# ══════════════════════════════════════════════════════════════════════════════════
with tab2:
    try:
        if env_df.empty:
            st.info("📁 환경 데이터 CSV를 사이드바에서 업로드해 주세요.")
        else:
            st.subheader(f"🌡️ {school_name} 환경 데이터 분석")
            env_cols = [c for c in ["temperature", "humidity", "ph", "ec"]
                        if c in env_df.columns]

            # ── 환경 요약 표 ──────────────────────────────────────────────────
            st.markdown("#### 📊 환경 요약 (평균 · 최소 · 최대)")
            summary_rows = []
            unit_s = {"temperature": "℃", "humidity": "%", "ph": "",
                      "ec": "mS/cm"}
            label_s = {"temperature": "온도", "humidity": "습도",
                       "ph": "pH", "ec": "EC"}
            for c in env_cols:
                s = env_df[c].dropna()
                if len(s) == 0:
                    continue
                summary_rows.append([
                    label_s[c],
                    f"{s.mean():.2f}{unit_s[c]}",
                    f"{s.min():.2f}{unit_s[c]}",
                    f"{s.max():.2f}{unit_s[c]}",
                    f"{len(s)}개"
                ])
            if summary_rows:
                st.table(pd.DataFrame(
                    summary_rows,
                    columns=["항목", "평균", "최소", "최대", "측정 횟수"]
                ))
            else:
                st.info("표시 가능한 환경 데이터가 없습니다.")

            # ── 날짜별 시계열 ─────────────────────────────────────────────────
            if "time" in env_df.columns:
                env_df_daily = env_df.copy()
                env_df_daily["date"] = env_df_daily["time"].dt.floor("D")
                st.markdown("#### 📈 날짜별 환경 변화 (일별 평균)")

                t_cols = [c for c in ["temperature", "humidity", "ph", "ec"]
                          if c in env_df.columns]
                if t_cols:
                    n = len(t_cols)
                    rows_n = (n + 1) // 2
                    fig_ts = make_subplots(rows=rows_n, cols=2)
                    colors  = {"temperature": "#D62728", "humidity": "#1F77B4",
                               "ph": "#2CA02C", "ec": "#9467BD"}
                    for idx, c in enumerate(t_cols):
                        d = env_df_daily.groupby("date")[c].mean().dropna()
                        if len(d) == 0:
                            continue
                        row_n = idx // 2 + 1
                        col_n = idx % 2 + 1
                        fig_ts.add_trace(
                            go.Scatter(
                                x=d.index, y=d.values,
                                mode="lines", name=c,
                                line=dict(color=colors.get(c, "#4C72B0"), width=2),
                                hovertemplate=(
                                    f"{c}: %{{y:.2f}}"
                                    f"{unit_s.get(c, '')}<extra></extra>"
                                )
                            ),
                            row=row_n, col=col_n
                        )
                    fig_ts.update_layout(
                        height=260 * rows_n,
                        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                        showlegend=False,
                        margin=dict(l=40, r=20, t=40, b=40)
                    )
                    st.plotly_chart(fig_ts, width="stretch")
                else:
                    st.info("표시할 환경 열이 없습니다.")

            # ── expander: 원본 테이블 + CSV 다운로드 ─────────────────────────
            with st.expander("📄 환경 데이터 원본 테이블 & CSV 다운로드"):
                st.dataframe(env_df, width="stretch")
                csv_bytes = env_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="환경 데이터 CSV 다운로드",
                    data=csv_bytes,
                    file_name="환경데이터.csv",
                    mime="text/csv"
                )

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 3 — 📊 생육 결과
# ══════════════════════════════════════════════════════════════════════════════════
with tab3:
    try:

        # ── 막대 그래프 함수 (재사용) ─────────────────────────────────────────
        def bar_chart(title, value_col, color):
            if value_col not in growth_df.columns:
                st.info(f"{value_col} 열이 없어 이 그래프를 표시할 수 없습니다.")
                return
            s = growth_df[value_col].dropna()
            if len(s) < 1:
                st.info("표시할 데이터가 부족합니다.")
                return
            ids = growth_df.loc[s.index, "개체번호"]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=ids.astype(str), y=s.values,
                marker_color=color, name=value_col,
                hovertemplate=(
                    f"{value_col}: %{{y:.2f}}"
                    "<extra>개체 %{x}</extra>"
                )
            ))
            bio_mean = None
            if "생중량" in growth_df.columns:
                bm = growth_df["생중량"].dropna().mean()
                if not pd.isna(bm):
                    bio_mean = bm
            if bio_mean is not None:
                fig.add_hline(
                    y=bio_mean,
                    line_dash="dot",
                    line_color="gray",
                    annotation_text=f"평균: {bio_mean:.2f}",
                    annotation_position="top right",
                    annotation_font=dict(
                        size=10,
                        family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"
                    )
                )
            base_layout(fig, title)
            fig.update_xaxes(
                tickangle=-45,
                tickfont=dict(size=7,
                              family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")
            )
            st.plotly_chart(fig, width="stretch")


        if growth_df.empty:
            st.info("📁 생육 결과 CSV를 사이드바에서 업로드해 주세요.")
        else:
            st.subheader(f"📊 {school_name} 생육 결과 분석")

            # ── 🥇 핵심 결과 카드 ────────────────────────────────────────────
            if "생중량" in growth_df.columns:
                bio_col   = growth_df["생중량"].dropna()
                if len(bio_col) > 0:
                    avg_bio   = bio_col.mean()
                    max_bio   = bio_col.max()
                    min_bio   = bio_col.min()
                    best_idx  = growth_df.loc[growth_df["생중량"].idxmax(), "개체번호"]
                    worst_idx = growth_df.loc[growth_df["생중량"].idxmin(), "개체번호"]
                    cv        = (bio_col.std() / avg_bio * 100) if avg_bio > 0 else 0.0

                    cc1, cc2, cc3, cc4 = st.columns(4)
                    with cc1:
                        st.metric("📦 평균 생중량", f"{avg_bio:.2f} g")
                    with cc2:
                        st.metric("🏆 최대 생중량", f"{max_bio:.2f} g (개체 {best_idx})")
                    with cc3:
                        st.metric("📉 최소 생중량", f"{min_bio:.2f} g (개체 {worst_idx})")
                    with cc4:
                        st.metric("📊 CV (변동계수)", f"{cv:.1f}%")
                else:
                    st.info("생중량 데이터가 없습니다.")
            else:
                st.info("생중량 열이 없습니다.")

            # ── 개체별 생육 비교 (막대 그래프) ────────────────────────────────
            st.markdown("#### 🌿 개체별 생육 비교 (막대 그래프)")

            bc1, bc2 = st.columns(2)
            with bc1:
                bar_chart("📦 개체별 평균 생중량 (g)", "생중량", "#D62728")
            with bc2:
                bar_chart("🍃 개체별 평균 잎 수 (장)", "잎 수", "#1F77B4")

            bc3, bc4 = st.columns(2)
            with bc3:
                bar_chart("📏 개체별 평균 지상부 길이 (mm)", "지상부 길이", "#2CA02C")
            with bc4:
                bar_chart("🌱 개체별 평균 지하부 길이 (mm)", "지하부 길이", "#9467BD")

            # ── 생중량 분포 (박스플롯) ────────────────────────────────────────
            st.markdown("#### 📦 생중량 분포 (박스플롯)")
            if "생중량" in growth_df.columns:
                bio_vals = growth_df["생중량"].dropna()
                if len(bio_vals) >= 2:
                    q75 = bio_vals.quantile(0.75)
                    q25 = bio_vals.quantile(0.25)
                    fig_box = go.Figure()
                    fig_box.add_trace(go.Box(
                        y=bio_vals.values,
                        fillcolor="#D62728",
                        line_color="#D62728",
                        name="생중량",
                        boxpoints="outliers",
                        marker=dict(color="#D62728", size=6),
                        hovertemplate="생중량: %{{y:.2f}} g<extra></extra>"
                    ))
                    fig_box.add_hline(
                        y=q75,
                        line_dash="dash",
                        line_color="orange",
                        annotation_text=f"상위 25% 경계: {q75:.2f} g",
                        annotation_font=dict(
                            size=9,
                            family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"
                        )
                    )
                    fig_box.add_hline(
                        y=q25,
                        line_dash="dash",
                        line_color="blue",
                        annotation_text=f"하위 25% 경계: {q25:.2f} g",
                        annotation_font=dict(
                            size=9,
                            family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"
                        )
                    )
                    base_layout(fig_box, "생중량 분포 (박스플롯)")
                    st.plotly_chart(fig_box, width="stretch")

                    top = growth_df.loc[growth_df["생중량"] >= q75, "생중량"].dropna()
                    bot = growth_df.loc[growth_df["생중량"] <= q25, "생중량"].dropna()
                    c5, c6 = st.columns(2)
                    with c5:
                        st.info(
                            f"🏆 **상위 25% 개체군** — 생중량 ≥ {q75:.2f} g\n"
                            f"   평균: {top.mean():.2f} g | 개수: {len(top)}개 | "
                            f"범위: {top.min():.2f} ~ {top.max():.2f} g"
                        )
                    with c6:
                        st.info(
                            f"📉 **하위 25% 개체군** — 생중량 ≤ {q25:.2f} g\n"
                            f"   평균: {bot.mean():.2f} g | 개수: {len(bot)}개 | "
                            f"범위: {bot.min():.2f} ~ {bot.max():.2f} g"
                        )
                else:
                    st.info("생중량 값이 2개 미만으로 분포를 표시할 수 없습니다.")
            else:
                st.info("생중량 열이 없어 분포를 표시할 수 없습니다.")

            # ── 상관관계 분석 ─────────────────────────────────────────────────
            st.markdown("#### 🔗 상관관계 분석 (산점도 + 추세선)")
            scat1, scat2 = st.columns(2)

            with scat1:
                if "잎 수" in growth_df.columns and "생중량" in growth_df.columns:
                    fig_sc1 = go.Figure()
                    r1 = scatter_with_r(
                        fig_sc1,
                        "잎 수 (장)",
                        "생중량 (g)",
                        growth_df["잎 수"].dropna(),
                        growth_df["생중량"].dropna(),
                        color="#1F77B4"
                    )
                    base_layout(fig_sc1, f"잎 수 vs 생중량  (r = {r1:.3f})")
                    st.plotly_chart(fig_sc1, width="stretch")
                else:
                    st.info("잎 수 또는 생중량 데이터가 없어 산점도를 표시할 수 없습니다.")

            with scat2:
                if "지상부 길이" in growth_df.columns and "생중량" in growth_df.columns:
                    fig_sc2 = go.Figure()
                    r2 = scatter_with_r(
                        fig_sc2,
                        "지상부 길이 (mm)",
                        "생중량 (g)",
                        growth_df["지상부 길이"].dropna(),
                        growth_df["생중량"].dropna(),
                        color="#2CA02C"
                    )
                    base_layout(fig_sc2, f"지상부 길이 vs 생중량  (r = {r2:.3f})")
                    st.plotly_chart(fig_sc2, width="stretch")
                else:
                    st.info("지상부 길이 또는 생중량 데이터가 없어 산점도를 표시할 수 없습니다.")

            # ── expander: 원본 데이터 + CSV 다운로드 ─────────────────────────
            with st.expander("📄 생육 데이터 원본 테이블 & CSV 다운로드"):
                st.dataframe(growth_df, width="stretch")
                csv_bytes = growth_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="생육 결과 CSV 다운로드",
                    data=csv_bytes,
                    file_name="생육결과.csv",
                    mime="text/csv"
                )

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
