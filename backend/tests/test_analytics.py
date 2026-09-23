import json
import unittest
from pathlib import Path
from app.analytics import summarize

class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.rows=json.loads((Path(__file__).parents[1]/'seed.json').read_text(encoding='utf-8'))

    def test_sample_metrics_are_separate(self):
        result=summarize(self.rows)
        self.assertEqual((result['count'],result['unique_days']),(180,90))
        series={s['metric']:s for s in result['series']}
        self.assertEqual(series['visits']['total'],493)
        self.assertEqual(series['pageviews']['total'],808)
        self.assertEqual(series['visits']['recent7'],35)
        self.assertEqual(series['visits']['previous7'],39)
        self.assertEqual(series['pageviews']['recent7'],60)
        self.assertEqual(series['pageviews']['previous7'],65)
        self.assertTrue(all(s['missing_days']==0 for s in series.values()))

    def test_missing_day_is_not_zero(self):
        rows=[r for r in self.rows if not (r['date']=='2026-09-12' and r['metric']=='visits')]
        series={s['metric']:s for s in summarize(rows)['series']}
        self.assertIsNone(series['visits']['recent7'])
        self.assertEqual(series['visits']['trend'],'데이터 부족')
        self.assertEqual(series['pageviews']['recent7'],60)

    def test_empty_and_zero_baseline(self):
        self.assertEqual(summarize([])['series'],[])
        rows=[{**r,'value':0} for r in self.rows]
        for s in summarize(rows)['series']:
            self.assertEqual(s['trend'],'유지')
            self.assertIsNone(s['change_percent'])

if __name__=='__main__': unittest.main()
