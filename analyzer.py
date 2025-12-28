#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Graph-based design quality analysis for
publish–subscribe microservice architectures.
"""

import json
from collections import defaultdict, Counter
from itertools import combinations
from typing import Dict, Set, List

import numpy as np

def percentile_threshold(values: List[int], percentile: int) -> float:
    if not values:
        return 0.0
    return float(np.percentile(values, percentile))


class Canalyzer:
    """
    Graph-based architectural quality analysis
    for publish–subscribe microservice systems.
    (Rapordaki yöntemle birebir uyumlu sürüm)
    """

    def __init__(self, data: Dict):
        self.data = data

        self.applications = [a["id"] for a in data["applications"]]
        self.topics = [t["id"] for t in data["topics"]]
        self.nodes = [n["id"] for n in data["nodes"]]

        rel = data["relationships"]
        self.publishes = rel["publishes_to"]
        self.subscribes = rel["subscribes_to"]
        self.runs_on = rel["runs_on"]

        # sonuçlar
        self.metrics = {}
        self.thresholds = {}

        self.AY = set()
        self.GB = set()
        self.AK = set()
        self.BM = set()

        self.MKon = set()
        self.DTHN = set()

        self.OZB = []
        self.DNG = []

    # -------------------------------------------------
    # Temel Kümeler (rapordaki notasyonlar)
    # -------------------------------------------------

    def _build_sets(self):
        Y_s = defaultdict(set)   # Y(s)
        A_s = defaultdict(set)   # A(s)
        Y_t = defaultdict(set)   # Y(t)
        A_t = defaultdict(set)   # A(t)
        S_n = defaultdict(set)   # S(n)

        for e in self.publishes:
            Y_s[e["from"]].add(e["to"])
            Y_t[e["to"]].add(e["from"])

        for e in self.subscribes:
            A_s[e["from"]].add(e["to"])
            A_t[e["to"]].add(e["from"])

        for e in self.runs_on:
            if e["from"].startswith("A"):
                S_n[e["to"]].add(e["from"])

        return Y_s, A_s, Y_t, A_t, S_n

    # -------------------------------------------------
    # Servis Seviyesi Metrikler (FORMEL UYUMLU)
    # -------------------------------------------------

    def _compute_service_metrics(self, Y_s, A_s, Y_t, A_t):
        metrics = {}

        for s in self.applications:
            # GD, CD, MK
            GD = len(A_s[s])
            CD = len(Y_s[s])
            MK = GD + CD

            # EO(s): doğrudan etkileşim kümesi
            EO = (
                set().union(*(A_t[t] for t in Y_s[s])) |
                set().union(*(Y_t[t] for t in A_s[s]))
            ) - {s}

            # DB(s): dolaylı bağımlılık (union, self yok)
            DB = len(
                set().union(*(A_t[t] for t in Y_s[s])) - {s}
            )

            # SY(s): tekil etkileşim noktaları
            SY = len(Y_s[s] | A_s[s])

            # YI(s): çift yönlü servis etkileşimi
            YI = len(EO)

            metrics[s] = {
                "GD": GD,
                "CD": CD,
                "MK": MK,
                "DB": DB,
                "SY": SY,
                "YI": YI,
                "EO": EO
            }

        return metrics

    # -------------------------------------------------
    # Eşikler (rapora uygun – ölçüt bazlı)
    # -------------------------------------------------

    def _compute_thresholds(self):
        THRESHOLDS = {
            "MK": 90,
            "DB": 85,
            "SY": 80,
            "YI": 90
        }

        thresholds = {}
        for key, pct in THRESHOLDS.items():
            values = [self.metrics[s][key] for s in self.applications]
            thresholds[key] = percentile_threshold(values, pct)

        return thresholds

    # -------------------------------------------------
    # Kural Tabanlı Servis Kokuları
    # -------------------------------------------------

    def _detect_service_smells(self):
        for s in self.applications:
            m = self.metrics[s]

            if (
                m["MK"] >= self.thresholds["MK"] and
                m["DB"] >= self.thresholds["DB"] and
                m["SY"] >= self.thresholds["SY"]
            ):
                self.AY.add(s)

            if (
                m["MK"] < self.thresholds["MK"] and
                m["DB"] >= self.thresholds["DB"]
            ):
                self.GB.add(s)

            if (
                m["YI"] >= self.thresholds["YI"] and
                m["MK"] >= self.thresholds["MK"]
            ):
                self.AK.add(s)

        self.BM = self.AY | self.GB | self.AK

    # -------------------------------------------------
    # Konu Seviyesi Risk (MKon)
    # -------------------------------------------------

    def _detect_topic_risks(self, Y_t, A_t):
        sub_counts = [len(A_t[t]) for t in self.topics]
        pub_counts = [len(Y_t[t]) for t in self.topics]

        sub_thr = percentile_threshold(sub_counts, 90)
        pub_thr = percentile_threshold(pub_counts, 90)

        for t in self.topics:
            if len(A_t[t]) >= sub_thr and len(Y_t[t]) >= pub_thr:
                self.MKon.add(t)

    # -------------------------------------------------
    # Düğüm Seviyesi Risk (DTHN)
    # -------------------------------------------------

    def _detect_node_risks(self, S_n):
        total_services = {n: len(S_n[n]) for n in self.nodes}
        risky_services = {
            n: len(S_n[n] & self.BM) for n in self.nodes
        }

        t_thr = percentile_threshold(list(total_services.values()), 90)
        r_thr = percentile_threshold(list(risky_services.values()), 90)

        for n in self.nodes:
            if total_services[n] >= t_thr and risky_services[n] >= r_thr:
                self.DTHN.add(n)

    # -------------------------------------------------
    # Döngüler (OZB, DNG)
    # -------------------------------------------------

    def _detect_cycles(self, Y_s, A_t):
        # OZB: servis kendi yayınladığı konuya abone
        for s in self.applications:
            for t in Y_s[s]:
                if s in A_t[t]:
                    self.OZB.append((s, t))

        # DNG: çift yönlü servis döngüsü
        for s1, s2 in combinations(self.applications, 2):
            for t1 in Y_s[s1]:
                for t2 in Y_s[s2]:
                    if s2 in A_t[t1] and s1 in A_t[t2]:
                        self.DNG.append((s1, s2, t1, t2))

    # -------------------------------------------------
    # ÇALIŞTIR
    # -------------------------------------------------

    def run_analysis(self):
        Y_s, A_s, Y_t, A_t, S_n = self._build_sets()

        self.metrics = self._compute_service_metrics(Y_s, A_s, Y_t, A_t)
        self.thresholds = self._compute_thresholds()

        self._detect_service_smells()
        self._detect_topic_risks(Y_t, A_t)
        self._detect_node_risks(S_n)
        self._detect_cycles(Y_s, A_t)

    # -------------------------------------------------
    # ÇIKTI
    # -------------------------------------------------

    def get_json_results(self):
        return {
            "metrics": self.metrics,
            "thresholds": self.thresholds,
            "AY": sorted(self.AY),
            "GB": sorted(self.GB),
            "AK": sorted(self.AK),
            "BM": sorted(self.BM),
            "MKon": sorted(self.MKon),
            "DTHN": sorted(self.DTHN),
            "OZB": self.OZB,
            "DNG": self.DNG
        }
    def get_json_results(self):
        serializable_metrics = {}

        for s, m in self.metrics.items():
            serializable_metrics[s] = {
                k: (sorted(list(v)) if isinstance(v, set) else v)
                for k, v in m.items()
            }

        return {
            "metrics": serializable_metrics,
            "thresholds": self.thresholds,
            "AY": sorted(self.AY),
            "GB": sorted(self.GB),
            "AK": sorted(self.AK),
            "BM": sorted(self.BM),
            "MKon": sorted(self.MKon),
            "DTHN": sorted(self.DTHN),
            "OZB": self.OZB,
            "DNG": self.DNG,
        }


    def generate_human_report(self):
        lines = []
        lines.append("=== Servis Düzeyinde Bulgular ===\n")

        for s in sorted(self.BM):
            lines.append(
                f"- Servis {s}, yüksek bakım maliyeti riski taşıyan "
                f"bir mimari yapı olarak sınıflandırılmıştır."
            )

            if s in self.AY:
                lines.append(
                    f"  * Aşırı Yüklenmiş Servis (AY): "
                    f"MK={self.metrics[s]['MK']}, "
                    f"DB={self.metrics[s]['DB']}, "
                    f"SY={self.metrics[s]['SY']} "
                    f"değerleri ilgili eşiklerin üzerindedir."
                )

            if s in self.GB:
                lines.append(
                    f"  * Gizli Bağımlılık (GB): "
                    f"DB={self.metrics[s]['DB']} yüksek olmasına rağmen "
                    f"MK={self.metrics[s]['MK']} görece düşüktür; "
                    f"servisin dolaylı bağımlılıkları belirgindir."
                )

            if s in self.AK:
                lines.append(
                    f"  * Aşırı Konuşkan Servis (AK): "
                    f"YI={self.metrics[s]['YI']} ve "
                    f"MK={self.metrics[s]['MK']} "
                    f"değerleri yüksektir; servis yoğun mesajlaşma göstermektedir."
                )

            lines.append("")

        if self.MKon:
            lines.append("=== Aşırı Merkezi Konu Başlıkları ===")
            for t in sorted(self.MKon):
                lines.append(
                    f"- Konu başlığı {t}, "
                    f"yüksek yayıncı ve abone yoğunluğu nedeniyle "
                    f"aşırı merkezi bir yapı sergilemektedir."
                )
            lines.append("")

        if self.DTHN:
            lines.append("=== Dağıtım Seviyesinde Tek Hata Noktaları ===")
            for n in sorted(self.DTHN):
                lines.append(
                    f"- Çalışma düğümü {n}, "
                    f"yüksek sayıda ve/veya kritik servis barındırması "
                    f"nedeniyle potansiyel tek hata noktasıdır."
                )
            lines.append("")

        return "\n".join(lines)


class BasicStatistics:
    """
    Calculates basic statistics from the dataset.
    """
    def __init__(self, data: Dict):
        self.data = data
        self.applications = data.get("applications", [])
        self.nodes = data.get("nodes", [])
        self.topics = data.get("topics", [])
        self.relationships = data.get("relationships", {})
        self.app_id_to_name = {app['id']: app['name'] for app in self.applications}
        self.node_id_to_name = {node['id']: node['name'] for node in self.nodes}
        self.topic_id_to_name = {topic['id']: topic['name'] for topic in self.topics}

    def get_node_application_counts(self):
        """Return nodes sorted by the number of applications running on them."""
        runs_on = self.relationships.get("runs_on", [])
        node_app_counts = Counter(edge["to"] for edge in runs_on if edge["from"].startswith("A"))
        for node in self.nodes:
            if node["id"] not in node_app_counts:
                node_app_counts[node["id"]] = 0
        return sorted(node_app_counts.items(), key=lambda item: item[1], reverse=True)

    def get_sorted_applications_by_topic_usage(self):
        """Return applications sorted by topic usage, with separate pub/sub counts."""
        publishes = self.relationships.get("publishes_to", [])
        subscribes = self.relationships.get("subscribes_to", [])
        
        pub_topics = defaultdict(set)
        for edge in publishes:
            pub_topics[edge["from"]].add(edge["to"])

        sub_topics = defaultdict(set)
        for edge in subscribes:
            sub_topics[edge["from"]].add(edge["to"])
            
        app_topic_counts = {}
        all_app_ids = {app['id'] for app in self.applications}
        
        for app_id in all_app_ids:
            pub_count = len(pub_topics.get(app_id, set()))
            sub_count = len(sub_topics.get(app_id, set()))
            app_topic_counts[app_id] = {
                "pub": pub_count,
                "sub": sub_count,
                "total": pub_count + sub_count
            }
            
        return sorted(app_topic_counts.items(), key=lambda item: item[1]["total"], reverse=True)

    def topics_by_size(self):
        """Returns topics sorted by size."""
        return sorted(self.topics, key=lambda t: t.get("size", 0), reverse=True)

    def top_published_topics(self):
        """Returns topics with the most publishers."""
        pub_counts = Counter(p["to"] for p in self.relationships.get("publishes_to", []))
        return sorted(pub_counts.items(), key=lambda item: item[1], reverse=True)

    def top_subscribed_topics(self):
        """Returns topics with the most subscribers."""
        sub_counts = Counter(s["to"] for s in self.relationships.get("subscribes_to", []))
        return sorted(sub_counts.items(), key=lambda item: item[1], reverse=True)

    def qos_statistics(self):
        """Returns statistics on QoS attributes."""
        qos_stats = {
            "durability": Counter(),
            "reliability": Counter(),
            "transport_priority": Counter()
        }
        for topic in self.topics:
            qos = topic.get("qos", {})
            if "durability" in qos:
                qos_stats["durability"][qos["durability"]] += 1
            if "reliability" in qos:
                qos_stats["reliability"][qos["reliability"]] += 1
            if "transport_priority" in qos:
                qos_stats["transport_priority"][qos["transport_priority"]] += 1
        return qos_stats

    def generate_report(self):
        """Generates a human-readable report of basic statistics."""
        lines = ["=== Temel İstatistikler ==="]

        lines.append("\n--- Konu Başlıkları (Boyuta Göre Sıralı) ---")
        for topic in self.topics_by_size():
            lines.append(f"- {self.topic_id_to_name.get(topic['id'], topic['id'])}: {topic['size']} bytes")

        lines.append("\n--- Konu Başlıkları (Yayıncı Sayısına Göre Sıralı) ---")
        for topic_id, count in self.top_published_topics():
            topic_name = self.topic_id_to_name.get(topic_id, topic_id)
            lines.append(f"- {topic_name}: {count} yayıncı")

        lines.append("\n--- Konu Başlıkları (Abone Sayısına Göre Sıralı) ---")
        for topic_id, count in self.top_subscribed_topics():
            topic_name = self.topic_id_to_name.get(topic_id, topic_id)
            lines.append(f"- {topic_name}: {count} abone")
        
        lines.append("\n--- Düğümlerdeki Uygulama Sayıları (Azalan Sırada) ---")
        for node_id, count in self.get_node_application_counts():
            node_name = self.node_id_to_name.get(node_id, node_id)
            lines.append(f"- {node_name}: {count} uygulama")

        lines.append("\n--- Uygulamaların Konu Kullanımı (Azalan Sırada) ---")
        for app_id, counts in self.get_sorted_applications_by_topic_usage():
            app_name = self.app_id_to_name.get(app_id, app_id)
            lines.append(f"- {app_name}: {counts['pub']} yayın, {counts['sub']} abonelik")

        lines.append("\n--- QoS İstatistikleri ---")
        qos = self.qos_statistics()
        for qos_type, values in qos.items():
            lines.append(f"  * {qos_type.capitalize()}:")
            for value, count in values.items():
                lines.append(f"    - {value}: {count}")

        return "\n".join(lines)
