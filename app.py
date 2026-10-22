"""Presentation only: every portfolio calculation lives in portfolio.py."""
import importlib
import io
from pathlib import Path
import streamlit as st
import portfolio

# Reload on every interaction so saved engine inputs immediately reach the app.
engine = importlib.reload(portfolio)
st.set_page_config(page_title='Portfolio Stability Decision', layout='wide')
st.title('Portfolio Stability Decision')
st.caption('Built with AI help, a learning demonstration, not investment advice.')
mode = st.sidebar.selectbox('Universe', ['Meridian training', 'My funds · VOO, SPY, BND, VB, BIL'])
personal = mode != 'Meridian training'
objective = st.sidebar.number_input('Objective return (%)', value=5.0 if personal else 6.5, step=.1, key=f'{mode}:objective') / 100
minimum = st.sidebar.number_input('Reserve minimum (%)', min_value=0.0, max_value=100.0, value=5.0 if personal else 3.0, step=1.0, key=f'{mode}:minimum') / 100
upload = st.sidebar.file_uploader('Monthly adjusted prices CSV', type='csv')
last_36 = st.sidebar.checkbox('Use only the last 36 monthly returns')
try:
    if upload or personal:
        csv_text = (upload.getvalue().decode('utf-8-sig') if upload else
                    Path(__file__).with_name('prices.csv').read_text(encoding='utf-8-sig'))
        names, loaded_returns, loaded_vols, loaded_corr, months = engine.estimate_csv(io.StringIO(csv_text))
        if last_36:
            _, returns, vols, corr, used = engine.estimate_csv(io.StringIO(csv_text), True)
        else:
            returns, vols, corr, used = loaded_returns, loaded_vols, loaded_corr, months
        defaults = [n == 'BIL' if personal and not upload else False for n in names]
        dataset = (upload.name if upload else 'Project 2 saved prices') + ':' + ','.join(names)
        st.caption(f'Historical estimates: arithmetic monthly mean × 12; sample standard deviation × √12. Current: {used} returns; loaded: {months}. History is not a forecast.')
        if months < 59:
            st.warning('This CSV has less than five years of monthly prices. Complete the required price history before checkout.')
        st.info('Tick the funds eligible under your reserve rule and enter your mandate objective and reserve minimum. This search enforces full investment, long-only weights, the return objective and the reserve minimum. Other mandate rules require separate checks.')
        if personal and not upload:
            st.caption('Saved Yahoo adjusted prices: Sep 2021–Sep 2026, downloaded Oct 22, 2026. BIL counts toward your 5% reserve. VOO and SPY track the same index; shifting between them need not change economic exposure much.')
    else:
        names = engine.ASSETS
        returns = loaded_returns = engine.RETURNS
        vols = loaded_vols = engine.VOLATILITIES
        corr = loaded_corr = engine.CORRELATIONS
        defaults = engine.RESERVE_ELIGIBLE
        dataset = 'Meridian'
        st.caption('Meridian: course-authored training estimates. Objective 6.5% assumes CPI 2.5% + 4%.')
        if last_36:
            st.info('The 36-month switch applies after uploading monthly prices.')
    edited, eligible = [], []
    for i, name in enumerate(names):
        left, right = st.columns([3, 1])
        # Separate window keys reset return boxes when the estimation window changes.
        edited.append(left.number_input(f'{name}: expected annual return (%)', value=float(returns[i] * 100), step=.1,
                                        key=f'{dataset}:{last_36}:{i}:{returns[i]}') / 100)
        eligible.append(right.checkbox('Reserve-eligible', value=defaults[i], key=f'{dataset}:reserve:{i}'))
    baseline = engine.search(loaded_returns, loaded_vols, loaded_corr, objective, eligible, minimum)
    current = engine.search(edited, vols, corr, objective, eligible, minimum)
    def show(column, title, result):
        column.subheader(title)
        if result is None:
            column.warning('no mix meets the objective')
            return
        column.table([{'Asset': name, 'Weight (%)': f'{weight * 100:.2f}'} for name, weight in zip(names, result['weights'])])
        column.write(f'Expected return: {result["return_estimate"] * 100:.2f}%')
        column.write(f'Volatility: {result["volatility"] * 100:.2f}%')
        column.write(f'Reserve-eligible weight: {result["reserve"] * 100:.2f}%')
    left, right = st.columns(2)
    show(left, 'Current inputs', current)
    show(right, 'As loaded · all months', baseline)
    st.caption('Both answers use the selected objective and reserve rule. The loaded answer keeps original return estimates and the full sample.')
    if current and baseline:
        change = max(abs(a - b) for a, b in zip(current['weights'], baseline['weights'])) * 100
        st.metric('Largest weight change (percentage points)', f'{change:.2f}')
    else:
        st.write('Largest weight change: unavailable unless both answers have a mix.')
except (ValueError, UnicodeError, OverflowError, OSError) as error:
    st.error(f'Input error: {error}')
