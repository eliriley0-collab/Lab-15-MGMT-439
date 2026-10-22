"""Course training inputs; all returns and weights are decimal fractions."""
import csv
import math
import statistics
from datetime import datetime

ASSETS = ['Treasury bills', 'Treasury 10-year note', 'Investment-grade bond fund', 'Global equity index fund']
RETURNS = [0.035, 0.043, 0.05, 0.08]
VOLATILITIES = [0.005, 0.07, 0.06, 0.16]
CORRELATIONS = [[1, .10, .05, 0], [.10, 1, .80, -.10], [.05, .80, 1, .25], [0, -.10, .25, 1]]
OBJECTIVE = .065
RESERVE_ELIGIBLE = [True, True, False, False]


def covariance_matrix(volatilities, correlations):
    n = len(volatilities)
    if len(correlations) != n or any(len(row) != n for row in correlations):
        raise ValueError('Correlation table must be square and match the assets.')
    if any(not math.isfinite(v) or v < 0 for v in volatilities):
        raise ValueError('Volatilities must be finite and nonnegative.')
    for i in range(n):
        for j in range(n):
            c = correlations[i][j]
            if not math.isfinite(c) or not -1 <= c <= 1:
                raise ValueError('Each correlation must be between -1 and 1.')
            if not math.isclose(c, correlations[j][i], abs_tol=1e-10):
                raise ValueError('Correlation table must be symmetric.')
        if not math.isclose(correlations[i][i], 1, abs_tol=1e-10):
            raise ValueError('Correlation diagonal must equal 1.')
    return [[correlations[i][j] * volatilities[i] * volatilities[j]
             for j in range(n)] for i in range(n)]


def expected_return(weights, returns):
    return sum(w * r for w, r in zip(weights, returns))


def portfolio_volatility(weights, covariance):
    variance = sum(weights[i] * weights[j] * covariance[i][j]
                   for i in range(len(weights)) for j in range(len(weights)))
    if variance < -1e-12:
        raise ValueError('Inputs produce a negative portfolio variance.')
    return math.sqrt(max(0, variance))


def reserve_weight(weights, eligible):
    return sum(w for w, counts in zip(weights, eligible) if counts)


def inverse_volatility(volatilities):
    scores = [1 / v for v in volatilities]
    return [s / sum(scores) for s in scores]


def search(returns, volatilities, correlations, objective, eligible, minimum):
    """Enumerate every fully invested long-only mix on a 5 percentage point grid."""
    n = len(returns)
    if not 1 <= n <= 6 or len(volatilities) != n or len(eligible) != n:
        raise ValueError('Supply matching inputs for one to six assets.')
    if not all(math.isfinite(r) for r in returns) or not math.isfinite(objective):
        raise ValueError('Return estimates and objective must be finite.')
    if not 0 <= minimum <= 1:
        raise ValueError('Reserve minimum must be between 0% and 100%.')
    covariance = covariance_matrix(volatilities, correlations)

    def mixes(slots, remaining):
        if slots == 1:
            yield [remaining / 20]
        else:
            for units in range(remaining + 1):
                for tail in mixes(slots - 1, remaining - units):
                    yield [units / 20] + tail

    best = None
    for weights in mixes(n, 20):
        ret = expected_return(weights, returns)
        reserve = reserve_weight(weights, eligible)
        if ret + 1e-12 < objective or reserve + 1e-12 < minimum:
            continue
        risk = portfolio_volatility(weights, covariance)
        if best is None or risk < best['volatility'] - 1e-12:
            best = dict(weights=weights, return_estimate=ret, volatility=risk, reserve=reserve)
    return best


def estimate_csv(source, last_36=False):
    """Sample SD; annualized arithmetic means; last 36 monthly RETURNS."""
    reader = csv.reader(source)
    header = next(reader, [])
    if not 4 <= len(header) <= 7 or len(set(header)) != len(header):
        raise ValueError('CSV needs a date column and 3–6 distinct ticker columns.')
    dates, prices = [], []
    for row in reader:
        if not row:
            continue
        if len(row) != len(header):
            raise ValueError('Every CSV row must have the same number of columns.')
        date = datetime.strptime(row[0].strip(), '%Y-%m-%d')
        values = [float(v) for v in row[1:]]
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError('Prices must be positive finite numbers, with no missing values.')
        month = date.year * 12 + date.month
        if dates and month != dates[-1] + 1:
            raise ValueError('Prices must be oldest first, one row per consecutive month.')
        dates.append(month)
        prices.append(values)
    if len(prices) < 3:
        raise ValueError('Need at least three monthly prices.')
    monthly = [[b / a - 1 for a, b in zip(previous, current)]
               for previous, current in zip(prices, prices[1:])]
    if last_36:
        if len(monthly) < 36:
            raise ValueError('Last 36 months needs at least 37 monthly price rows.')
        monthly = monthly[-36:]
    columns = list(zip(*monthly))
    means = [statistics.mean(c) * 12 for c in columns]
    vols = [statistics.stdev(c) * math.sqrt(12) for c in columns]
    def correlation(a, b):
        centered_a = [x - statistics.mean(a) for x in a]
        centered_b = [x - statistics.mean(b) for x in b]
        denominator = math.sqrt(sum(x*x for x in centered_a) * sum(x*x for x in centered_b))
        return sum(x*y for x, y in zip(centered_a, centered_b)) / denominator

    corr = [[(1.0 if i == j else 0.0) if vols[i] < 1e-12 or vols[j] < 1e-12
             else max(-1, min(1, correlation(a, b)))
             for j, b in enumerate(columns)] for i, a in enumerate(columns)]
    return header[1:], means, vols, corr, len(monthly)


def main():
    covariance = covariance_matrix(VOLATILITIES, CORRELATIONS)
    portfolios = [('Benchmark', [0, 0, .4, .6]), ('Equal weight', [.25] * 4),
                  ('Inverse volatility', inverse_volatility(VOLATILITIES))]
    for name, weights in portfolios:
        ret = expected_return(weights, RETURNS)
        print(name)
        print('Weights (%): ' + ' / '.join(f'{w * 100:.1f}' for w in weights))
        print(f'Expected return: {ret * 100:.2f}%')
        print(f'Volatility: {portfolio_volatility(weights, covariance) * 100:.2f}%')
        print(f'Reserve-eligible weight: {reserve_weight(weights, RESERVE_ELIGIBLE) * 100:.1f}%')
        print(f'Meets {OBJECTIVE * 100:.1f}% objective: {"yes" if ret >= OBJECTIVE else "no"}\n')


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        raise SystemExit(f'Input error: {error}')
