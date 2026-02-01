# Yayınla–Abone Ol Tabanlı Dağıtık Sistemlerde Yapısal Etkileşim Örüntülerinin Çizge Tabanlı Statik Analizi

## İçindekiler

1. [Çözülen Problem](#1-çözülen-problem)
2. [Temel Yaklaşım](#2-temel-yaklaşım)
3. [Çizge Tabanlı Temsil](#3-çizge-tabanlı-temsil)
4. [Yapısal Kalite Metrikleri](#4-yapısal-kalite-metrikleri)
5. [Göreli Yorumlama ve Kural Tabanlı Değerlendirme](#5-göreli-yorumlama-ve-kural-tabanlı-değerlendirme)
6. [Birleşik Aykırılık Skoru](#6-birleşik-aykırılık-skoru)
7. [Dataset Senaryoları ve Beklenen Davranışlar](#7-dataset-senaryoları-ve-beklenen-davranışlar)
8. [Bulgular ve Sonuçlar Bölümünün Hazırlanması](#8-bulgular-ve-sonuçlar-bölümünün-hazırlanması)

---

## 1. Çözülen Problem

### 1.1. Problem Tanımı

Yayınla–abone ol (publish–subscribe) mimarisi, modern dağıtık sistemlerde ölçeklenebilirlik ve esneklik sağlamak amacıyla yaygın olarak kullanılmaktadır. Bu mimaride:

- **Yayıncılar (Publishers):** Belirli konulara (topics) mesaj gönderen uygulamalar
- **Aboneler (Subscribers):** Belirli konulardan mesaj alan uygulamalar
- **Konular (Topics):** Uygulamalar arası dolaylı iletişimi sağlayan kanallar

**Temel Problem:** Bu mimari çalışma zamanında gevşek bağlanma (loose coupling) sağlarken, tasarım seviyesinde şu zorluklara yol açmaktadır:

| Zorluk | Açıklama |
|--------|----------|
| **Örtük Etkileşimler** | Uygulamalar doğrudan birbirleriyle değil, konular üzerinden iletişim kurduğundan etkileşimler görünmezdir |
| **Gizli Bağımlılıklar** | Hangi uygulamanın hangi uygulamaya bağımlı olduğu doğrudan anlaşılamaz |
| **Yapısal Yoğunlaşmalar** | Zamanla bazı uygulamalar veya konular mimari açıdan kritik/problemli hale gelebilir |
| **Analiz Güçlüğü** | Mimarinin bütüncül değerlendirilmesi ve evriminin takibi zorlaşır |

### 1.2. Motivasyon

```
┌─────────────────────────────────────────────────────────────┐
│                    Geleneksel Görünüm                        │
│                                                              │
│   [App A] ──publish──> [Topic X] <──subscribe── [App B]     │
│                                                              │
│   "App A ve App B birbirinden bağımsız görünüyor"           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     Gerçek Durum                             │
│                                                              │
│   [App A] ════════════════════════════════> [App B]         │
│            (Dolaylı veri bağımlılığı var!)                  │
│                                                              │
│   App A'daki değişiklik App B'yi etkiler                    │
└─────────────────────────────────────────────────────────────┘
```

### 1.3. Çalışmanın Hedefleri

Bu çalışma aşağıdaki hedefleri gerçekleştirmeyi amaçlamaktadır:

1. **Örtük Etkileşimleri Görünür Kılma:** Statik analiz yoluyla tüm yayınla-abone ol ilişkilerini tespit etme
2. **Yapısal Temsil Oluşturma:** Çizge tabanlı bir mimari model kurma
3. **Nicel Ölçütler Tanımlama:** Mimari yapının farklı boyutlarını ölçen metrikler geliştirme
4. **Göreli Değerlendirme:** Sistem içi karşılaştırmalarla aykırılıkları belirleme
5. **Yapısal Sinyaller Üretme:** Mimari değerlendirme süreçlerini destekleyen göstergeler sunma

> **ÖNEMLİ:** Bu yaklaşım doğrudan "hata" veya "kusur" tespiti yapmaz. Bunun yerine, sistemin kendi iç bağlamına göre "alışılmadık" yapısal yoğunlaşmaları görünür kılar.

---

## 2. Temel Yaklaşım

### 2.1. Metodoloji Genel Bakış

Yaklaşım üç ana adımdan oluşmaktadır:

```
┌──────────────────────────────────────────────────────────────────────┐
│                         METODOLOJI                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐   │
│  │   ADIM 1        │    │   ADIM 2        │    │   ADIM 3        │   │
│  │                 │    │                 │    │                 │   │
│  │  Statik Analiz  │───>│  Çizge Temsili  │───>│  Kural Tabanlı  │   │
│  │  ile İlişki     │    │  üzerinde       │    │  Göreli         │   │
│  │  Çıkarımı       │    │  Metrik         │    │  Değerlendirme  │   │
│  │                 │    │  Hesaplama      │    │                 │   │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘   │
│         │                      │                      │              │
│         ▼                      ▼                      ▼              │
│  • Kaynak kod analizi   • Yapısal metrikler   • Q1/Q3 eşikleri      │
│  • publish/subscribe    • Uygulama düzeyi     • Örüntü tespiti      │
│    çağrılarının         • Konu düzeyi         • Birleşik skor       │
│    tespiti              • Düğüm düzeyi        • Önceliklendirme     │
│  • Çağrı grafiği        • Kütüphane düzeyi                          │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2. Statik Analiz Yaklaşımı

**Giriş Noktası Tabanlı Analiz:**
- Ana yürütme noktasından (main metodu) başlanır
- Ulaşılabilir çağrı zincirleri takip edilir
- Yalnızca çalışma zamanında tetiklenmesi muhtemel çağrılar dahil edilir

**Polimorfizm Desteği:**
- Arayüzler ve soyut sınıflar üzerinden yapılan çağrılar çözümlenir
- Dinamik bağlanma ile gerçekleşen etkileşimler de modele yansıtılır

**Geri Çağırım Mekanizmaları:**
- Abonelik sırasında kayıt edilen callback metotları analiz edilir
- Çerçeve tarafından tetiklenen dolaylı kontrol akışları soyutlanır

---

## 3. Çizge Tabanlı Temsil

### 3.1. Temsil Yapısı

Sistem, yönlü ve etiketli bir çizge olarak modellenir:

```
                    ┌─────────────────────────────────────────┐
                    │           ÇİZGE TEMSİLİ                 │
                    └─────────────────────────────────────────┘

    ┌──────────┐                                    ┌──────────┐
    │ Çalışma  │                                    │ Çalışma  │
    │ Düğümü   │◄─────────runs_on─────────────────► │ Düğümü   │
    │   N0     │                                    │   N1     │
    └────▲─────┘                                    └────▲─────┘
         │                                               │
         │ runs_on                                       │ runs_on
         │                                               │
    ┌────┴─────┐         ┌──────────┐            ┌──────┴──────┐
    │ Uygulama │         │  Konu    │            │  Uygulama   │
    │    A0    │─publish─►│   T0    │◄─subscribe─│     A1      │
    └────┬─────┘         └──────────┘            └─────────────┘
         │
         │ uses
         ▼
    ┌──────────┐
    │ Kütüphane│
    │   L0     │
    └──────────┘
```

### 3.2. Düğüm Türleri

| Düğüm Türü | Sembol | Açıklama |
|------------|--------|----------|
| **Uygulama** | $a \in \mathcal{A}$ | Dağıtık sistemde yer alan bağımsız uygulamalar |
| **Konu** | $t \in \mathcal{T}$ | Uygulamalar arası asenkron iletişim kanalları |
| **Çalışma Düğümü** | $n \in \mathcal{N}$ | Fiziksel veya sanal sunucular |
| **Kütüphane** | $l \in \mathcal{L}$ | Ortak kullanılan yazılım bileşenleri |

### 3.3. Kenar Türleri ve İlişkiler

| İlişki | Yön | Anlam |
|--------|-----|-------|
| **publishes_to** | Uygulama → Konu | Uygulama bu konuya mesaj yayınlıyor |
| **subscribes_to** | Uygulama → Konu | Uygulama bu konuya abone |
| **runs_on** | Uygulama → Düğüm | Uygulama bu düğümde çalışıyor |
| **uses** | Uygulama → Kütüphane | Uygulama bu kütüphaneyi kullanıyor |

### 3.4. Temel Notasyonlar

```
┌────────────────────────────────────────────────────────────────┐
│                      NOTASYON TABLOSU                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Y(a) ⊆ T  : Uygulama a tarafından yayın yapılan konular      │
│  A(a) ⊆ T  : Uygulama a tarafından abone olunan konular       │
│                                                                │
│  Y(t) ⊆ A  : Konu t'ye yayın yapan uygulamalar                │
│  A(t) ⊆ A  : Konu t'ye abone olan uygulamalar                 │
│                                                                │
│  S(n) ⊆ A  : Çalışma düğümü n üzerindeki uygulamalar          │
│                                                                │
│  L(a) ⊆ L  : Uygulama a'nın kullandığı kütüphaneler           │
│  U(l) ⊆ A  : Kütüphane l'yi kullanan uygulamalar              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. Yapısal Kalite Metrikleri

### 4.1. Uygulama Düzeyinde Metrikler

#### 4.1.1. Etki Alanı (R — Reach)

**Formül:**
$$R(a) = \big|\{ a' \in \mathcal{A} \setminus \{a\} \mid (\exists t \in Y(a): a' \in A(t)) \lor (\exists t \in A(a): a' \in Y(t)) \}\big|$$

**Bu formül ne buluyor?**

Bir uygulamanın, yayın yaptığı veya abone olduğu konular aracılığıyla **kendisi dışındaki** uygulamalarla kurduğu benzersiz etkileşimlerin toplam sayısını hesaplar.

**Detaylı Açıklama:**

1. **İlk koşul** $(\exists t \in Y(a): a' \in A(t))$: 
   - "Uygulama $a$'nın yayın yaptığı en az bir konu $t$ var ki, $a'$ uygulaması bu konuya abone"
   - Yani $a$ → $t$ → $a'$ şeklinde bir veri akışı mümkün

2. **İkinci koşul** $(\exists t \in A(a): a' \in Y(t))$:
   - "Uygulama $a$'nın abone olduğu en az bir konu $t$ var ki, $a'$ uygulaması bu konuya yayın yapıyor"
   - Yani $a'$ → $t$ → $a$ şeklinde bir veri akışı mümkün

3. **$\setminus \{a\}$**: Kendisi hariç tutulur (self-loop sayılmaz)

**Örnek Hesaplama:**

```
Sistem:
  A0 ──publish──> T0 <──subscribe── A1
  A0 ──publish──> T1 <──subscribe── A2
  A0 ──subscribe──> T2 <──publish── A3

R(A0) hesabı:
  - Y(A0) = {T0, T1}
  - A(A0) = {T2}
  
  T0 üzerinden: A(T0) = {A1} → A1 ile etkileşim
  T1 üzerinden: A(T1) = {A2} → A2 ile etkileşim
  T2 üzerinden: Y(T2) = {A3} → A3 ile etkileşim
  
  R(A0) = |{A1, A2, A3}| = 3
```

**Yorumlama:**
- **Yüksek R:** Uygulama mimari içinde geniş bir etki alanına sahip, potansiyel olarak "hub" rolünde
- **Düşük R:** Uygulama izole veya sınırlı etkileşimli

---

#### 4.1.2. Yoğunlaştırma (A — Amplification)

**Formül:**
$$A(a) = \frac{R(a)}{|Y(a)| + 1}$$

**Bu formül ne buluyor?**

Bir uygulamanın **sınırlı sayıda yayın kanalı** üzerinden ne ölçüde **geniş bir etki alanı** oluşturduğunu ölçer.

**Detaylı Açıklama:**

- **Pay**: Etki alanı (R) — kaç farklı uygulamaya ulaşılıyor
- **Payda**: Yayın yapılan konu sayısı + 1
- **+1**: Sıfıra bölme hatasını önlemek ve hiç yayın yapmayan uygulamaları da değerlendirmek için

**Neden sadece yayın kanalları?**

Bu metrik özellikle **yayıncı rolündeki** uygulamaların etkinliğini ölçer. Bir uygulama az sayıda konuya yayın yaparak çok sayıda uygulamaya ulaşabiliyorsa, bu "yoğunlaştırma" etkisi gösterir.

**Örnek Hesaplama:**

```
Senaryo 1: Yüksek Yoğunlaştırma
  A0: Y(A0) = {T0}  (1 konuya yayın)
      R(A0) = 10    (10 uygulamaya ulaşıyor)
  A(A0) = 10 / (1 + 1) = 5.0

Senaryo 2: Düşük Yoğunlaştırma  
  A1: Y(A1) = {T0, T1, T2, T3, T4}  (5 konuya yayın)
      R(A1) = 10                    (10 uygulamaya ulaşıyor)
  A(A1) = 10 / (5 + 1) = 1.67
```

**Yorumlama:**
- **Yüksek A:** Az kanal ile çok etkileşim — merkezi/kritik yayın noktası
- **Düşük A:** Etki alanı kanal sayısıyla orantılı — dağınık etkileşim

---

#### 4.1.3. Rol Asimetrisi (RA — Role Asymmetry)

**Formül:**
$$RA(a) = \frac{|Y(a)| - |A(a)|}{|Y(a)| + |A(a)| + 1}$$

**Bu formül ne buluyor?**

Bir uygulamanın **üretici (yayıncı)** ve **tüketici (abone)** rollerindeki dengesizliğini ölçer.

**Detaylı Açıklama:**

- **Değer aralığı:** $(-1, +1)$ 
- **Pozitif değer:** Yayıncı ağırlıklı (daha çok yayın, az abonelik)
- **Negatif değer:** Abone ağırlıklı (daha çok abonelik, az yayın)
- **Sıfıra yakın:** Dengeli rol dağılımı

**Matematiksel Özellikler:**

```
RA değeri    | Anlam
-------------|----------------------------------------
RA ≈ +1      | Neredeyse sadece yayıncı (saf üretici)
RA ≈ 0       | Dengeli (hem yayıncı hem abone)
RA ≈ -1      | Neredeyse sadece abone (saf tüketici)
```

**Örnek Hesaplama:**

```
A0: Y(A0) = {T0, T1, T2, T3}  (4 yayın)
    A(A0) = {T4}              (1 abonelik)
RA(A0) = (4 - 1) / (4 + 1 + 1) = 3/6 = 0.5  (Yayıncı ağırlıklı)

A1: Y(A1) = {T0}              (1 yayın)
    A(A1) = {T1, T2, T3, T4}  (4 abonelik)
RA(A1) = (1 - 4) / (1 + 4 + 1) = -3/6 = -0.5  (Abone ağırlıklı)
```

**Yorumlama:**
- **Aşırı pozitif/negatif:** Tek yönlü bağımlılık, modülerlik sorunu olabilir
- **Sıfıra yakın:** Uygulama hem veri üretiyor hem tüketiyor — daha entegre

---

#### 4.1.4. Bağlam Çeşitliliği (TC — Topic Context Diversity)

**Formül:**
$$TC(a) = \big| \{ \text{kategori}(t) \mid t \in Y(a) \cup A(a) \} \big|$$

**Bu formül ne buluyor?**

Bir uygulamanın etkileşimde bulunduğu konuların **kaç farklı işlevsel bağlama/kategoriye** yayıldığını hesaplar.

**Detaylı Açıklama:**

Konu kategorileri, isimlendirme şemalarındaki hiyerarşik öneklerden türetilir:

```
Konu İsimleri              | Kategori (LCP tabanlı)
---------------------------|------------------------
nav.track.update           | nav.track
nav.track.delete           | nav.track
sensor.fusion.raw          | sensor.fusion
sensor.fusion.filtered     | sensor.fusion
weapons.control.fire       | weapons.control
```

**Kategori Çıkarım Algoritması (LCP — Longest Common Prefix):**

```python
# Her konu için, diğer konularla en uzun ortak önek bulunur
# MIN_LCP_LEN = 3 (minimum önek uzunluğu)

Örnek:
  T0: "nav.track.update"
  T1: "nav.track.delete"
  
  LCP(T0, T1) = "nav.track." → Kategori: "nav.track"
```

**Örnek Hesaplama:**

```
A0'ın etkileştiği konular:
  - nav.track.update     → kategori: "nav"
  - sensor.fusion.raw    → kategori: "sensor"
  - weapons.control.fire → kategori: "weapons"
  - log.system.error     → kategori: "log"

TC(A0) = |{nav, sensor, weapons, log}| = 4
```

**Yorumlama:**
- **Yüksek TC:** Uygulama birçok farklı alan/modülle etkileşiyor — potansiyel "God Class" veya entegrasyon noktası
- **Düşük TC:** Uygulama tek bir alana odaklı — iyi kohezyon

---

#### 4.1.5. Kütüphane Maruziyeti (LE — Library Exposure)

**Formül:**
$$LE(a) = |L(a)|$$

**Bu formül ne buluyor?**

Bir uygulamanın kullandığı **ortak kütüphanelerin sayısını** hesaplar.

**Detaylı Açıklama:**

- Basit bir sayım metriği
- Ortak kütüphaneler, birden fazla uygulama tarafından paylaşılan yazılım bileşenleridir
- Yüksek kütüphane kullanımı, daha fazla bağımlılık ve potansiyel değişiklik etkisi anlamına gelir

**Örnek:**

```
A0 kullanıyor: {common-utils, logging-lib, network-core}
LE(A0) = 3

A1 kullanıyor: {logging-lib}
LE(A1) = 1
```

**Yorumlama:**
- **Yüksek LE:** Çok sayıda ortak bağımlılık — değişikliklerden etkilenme riski
- **Düşük LE:** Az bağımlılık — daha izole

---

### 4.2. Konu Düzeyinde Metrikler

#### 4.2.1. Kapsayıcılık (C — Coverage)

**Formül:**
$$C(t) = |A(t)| + |Y(t)|$$

**Bu formül ne buluyor?**

Bir konunun etkileşimde bulunduğu **toplam uygulama sayısını** (hem yayıncılar hem aboneler) hesaplar.

**Detaylı Açıklama:**

- **|A(t)|**: Konuya abone olan uygulama sayısı
- **|Y(t)|**: Konuya yayın yapan uygulama sayısı
- Toplam, konunun "trafiğini" veya "popülerliğini" gösterir

**Örnek:**

```
T0 (core.sync.update):
  Yayıncılar: {A0, A1, A2, A3}  → |Y(T0)| = 4
  Aboneler:   {A1, A2, A3, A4}  → |A(T0)| = 4
  
C(T0) = 4 + 4 = 8
```

**Yorumlama:**
- **Yüksek C:** Konu sistem genelinde yaygın kullanılıyor — kritik iletişim kanalı
- **Düşük C:** Konu az sayıda uygulama arasında — özel/izole kanal

---

#### 4.2.2. Dengesizlik (I — Imbalance)

**Formül:**
$$I(t) = \frac{\big||A(t)| - |Y(t)|\big|}{|A(t)| + |Y(t)| + 1}$$

**Bu formül ne buluyor?**

Bir konunun **yayıncı ve abone dağılımındaki dengesizliği** ölçer.

**Detaylı Açıklama:**

- **Değer aralığı:** $[0, 1)$
- **0'a yakın:** Dengeli dağılım (yaklaşık eşit yayıncı ve abone)
- **1'e yakın:** Aşırı dengesiz (ya çok yayıncı ya çok abone)

**Matematiksel Özellikler:**

```
Durum                    | I değeri | Anlam
-------------------------|----------|---------------------------
|Y| = |A|                | 0        | Mükemmel denge
|Y| >> |A| veya |A| >> |Y| | ~1     | Tek yönlü kanal
```

**Örnek Hesaplama:**

```
T0: Y(T0) = {A0}          (1 yayıncı)
    A(T0) = {A1, A2, A3, A4}  (4 abone)
I(T0) = |1 - 4| / (1 + 4 + 1) = 3/6 = 0.5

T1: Y(T1) = {A0, A1}      (2 yayıncı)
    A(T1) = {A2, A3}      (2 abone)
I(T1) = |2 - 2| / (2 + 2 + 1) = 0/5 = 0
```

**Yorumlama:**
- **Yüksek I:** Yönlü yoğunlaşma — broadcast (1→N) veya collector (N→1) deseni
- **Düşük I:** Çift yönlü veya dengeli kullanım

---

#### 4.2.3. Fiziksel Yayılım (PS — Physical Spread)

**Formül:**
$$PS(t) = \big| \{ n \in \mathcal{N} \mid \exists a \in A(t) \cup Y(t),\ a \in S(n) \} \big|$$

**Bu formül ne buluyor?**

Bir konunun etkileşimde bulunduğu uygulamaların **kaç farklı çalışma düğümüne** yayıldığını hesaplar.

**Detaylı Açıklama:**

Bu formül şunu sorar: "Bu konu üzerinden haberleşen uygulamalar kaç farklı fiziksel/sanal makineye dağılmış?"

**Örnek Hesaplama:**

```
Sistem yerleşimi:
  N0: {A0, A1}
  N1: {A2, A3}
  N2: {A4}

T0 ile etkileşen uygulamalar: {A0, A2, A4}

PS(T0) hesabı:
  A0 → N0'da
  A2 → N1'de
  A4 → N2'de
  
PS(T0) = |{N0, N1, N2}| = 3
```

**Yorumlama:**
- **Yüksek PS:** Konu düğümler arası (cross-node) iletişim sağlıyor — ağ trafiği
- **Düşük PS:** Konu yerel iletişim için kullanılıyor — düğüm içi

---

### 4.3. Çalışma Düğümü Düzeyinde Metrikler

#### 4.3.1. Düğüm Yoğunluğu (ND — Node Density)

**Formül:**
$$ND(n) = |S(n)|$$

**Bu formül ne buluyor?**

Bir çalışma düğümü üzerinde **konumlanan uygulama sayısını** hesaplar.

**Örnek:**

```
N0 üzerinde çalışan uygulamalar: {A0, A1, A2, A3, A4}
ND(N0) = 5

N1 üzerinde çalışan uygulamalar: {A5, A6}
ND(N1) = 2
```

**Yorumlama:**
- **Yüksek ND:** Düğüm üzerinde yoğun uygulama dağılımı — kaynak rekabeti, yük dengeleme sorunu
- **Düşük ND:** Az uygulama — yetersiz kaynak kullanımı veya izole düğüm

---

#### 4.3.2. Düğüm İçi Etkileşim Yoğunluğu (NID — Node Interaction Density)

**Önce etkileşim ilişkisi tanımı:**
$$a_i \leftrightarrow a_j \iff \exists t \in \mathcal{T} : (a_i \in Y(t) \land a_j \in A(t)) \lor (a_j \in Y(t) \land a_i \in A(t))$$

**Ana formül:**
$$NID(n) = \big| \{ (a_i,a_j) \subseteq S(n) \mid a_i \leftrightarrow a_j \} \big|$$

**Bu formül ne buluyor?**

Aynı çalışma düğümü üzerinde yer alan uygulamalar arasındaki **mantıksal etkileşim sayısını** hesaplar.

**Detaylı Açıklama:**

1. **Etkileşim koşulu**: İki uygulama, en az bir konu üzerinden yayınla-abone ilişkisi kuruyorsa "etkileşimde" kabul edilir
2. **Düğüm içi sınırlandırma**: Sadece aynı düğümdeki uygulama çiftleri değerlendirilir
3. **Yönsüz sayım**: $(a_i, a_j)$ ve $(a_j, a_i)$ aynı etkileşim olarak sayılır

**Örnek Hesaplama:**

```
N0 üzerindeki uygulamalar: {A0, A1, A2}

Etkileşim kontrolleri:
  (A0, A1): A0 T0'a yayın yapıyor, A1 T0'a abone → Etkileşim VAR
  (A0, A2): Ortak konu yok → Etkileşim YOK
  (A1, A2): A1 T1'e yayın, A2 T1'e abone → Etkileşim VAR

NID(N0) = |{(A0,A1), (A1,A2)}| = 2
```

**Yorumlama:**
- **Yüksek NID:** Düğüm içinde yoğun mesajlaşma — yerel iletişim kümesi
- **Düşük NID:** Uygulamalar aynı düğümde ama az etkileşiyor — yalnızca fiziksel birliktelik

---

### 4.4. Kütüphane Düzeyinde Metrikler

#### 4.4.1. Kütüphane Yaygınlığı (LC — Library Coverage)

**Formül:**
$$LC(l) = |U(l)|$$

**Bu formül ne buluyor?**

Bir kütüphaneyi kullanan **uygulama sayısını** hesaplar.

**Örnek:**

```
common-utils kütüphanesini kullanan uygulamalar: {A0, A1, A2, A3, A4, A5}
LC(common-utils) = 6
```

**Yorumlama:**
- **Yüksek LC:** Yaygın kullanılan kütüphane — değişiklik etkisi geniş
- **Düşük LC:** Az kullanılan kütüphane — sınırlı etki

---

#### 4.4.2. Kütüphane Yoğunlaşması (LCon — Library Concentration)

**Formül:**
$$LCon(l) = \max_{n \in \mathcal{N}} \big| S(n) \cap U(l) \big|$$

**Bu formül ne buluyor?**

Bir kütüphanenin kullanımının çalışma düğümleri üzerindeki **maksimum yerel yoğunlaşmasını** hesaplar.

**Detaylı Açıklama:**

Bu formül şunu sorar: "Bu kütüphaneyi kullanan en çok uygulama hangi düğümde ve kaç tane?"

**Örnek Hesaplama:**

```
Kütüphane L0'ı kullanan uygulamalar: {A0, A1, A2, A3, A4}

Düğüm yerleşimi:
  N0: {A0, A1, A2}  → L0 kullananlar: {A0, A1} → 2
  N1: {A3, A4, A5}  → L0 kullananlar: {A3, A4} → 2
  N2: {A6}          → L0 kullananlar: {} → 0

LCon(L0) = max(2, 2, 0) = 2
```

**Yorumlama:**
- **Yüksek LCon:** Kütüphane belirli düğümlerde yoğunlaşmış — yerel bağımlılık kümesi
- **Düşük LCon:** Kütüphane kullanımı düğümlere eşit dağılmış

---

## 5. Göreli Yorumlama ve Kural Tabanlı Değerlendirme

### 5.1. Göreli Metrik Yorumlama

Mutlak eşikler yerine, sistemin kendi içindeki dağılıma dayalı göreli yorumlama kullanılır:

**Formül:**
$$M(x)\!\uparrow \iff M(x) > Q_3(M)$$
$$M(x)\!\downarrow \iff M(x) < Q_1(M)$$

Burada:
- $Q_1$: Birinci çeyrek (25. yüzdelik)
- $Q_3$: Üçüncü çeyrek (75. yüzdelik)

**Bu yaklaşım ne sağlıyor?**

```
┌──────────────────────────────────────────────────────────────────┐
│                    GÖRELI YORUMLAMA                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Metrik değerleri sıralandığında:                               │
│                                                                  │
│  ┌─────┬─────────────┬─────────────────────┬─────────────┬─────┐│
│  │ MIN │    Q1       │       MEDIAN        │     Q3      │ MAX ││
│  └─────┴─────────────┴─────────────────────┴─────────────┴─────┘│
│         ↑                                        ↑               │
│    "Düşük" (↓)                              "Yüksek" (↑)         │
│                                                                  │
│  Ortadaki %50'lik dilim: "Normal"                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Neden Göreli?**

1. **Sistem bağlamına duyarlılık:** Her sistemin kendi normali var
2. **Ölçekten bağımsızlık:** 10 uygulamalı sistemle 1000 uygulamalı sistem karşılaştırılabilir
3. **Aykırılık odağı:** Sadece "sistemin geneliyle uyumsuz" olanlar işaretlenir

---

### 5.2. Yapısal Aykırılık Örüntüleri

Birden fazla metriğin birlikte değerlendirilmesiyle tanımlanan örüntüler:

#### 5.2.1. Uygulama Düzeyi Örüntüler

| Örüntü | Koşul | Anlam |
|--------|-------|-------|
| **Geniş Etki Alanı (WR)** | $R(a)\!\uparrow \land A(a)\!\uparrow$ | Çok sayıda uygulamaya az kanal ile ulaşan hub |
| **Rol Dengesizliği (RS)** | $RA(a)\!\uparrow \lor RA(a)\!\downarrow$ | Aşırı yayıncı veya aşırı abone |
| **Bağlam Yayılımı (CS)** | $TC(a)\!\uparrow$ | Çok farklı alanda etkileşim — potansiyel God Class |
| **Ortak Bağımlılık Maruziyeti (SD)** | $LE(a)\!\uparrow$ | Çok sayıda ortak kütüphaneye bağımlı |

**Geniş Etki Alanı (Wide Reach) Detaylı Açıklama:**

```
WR örüntüsü: R↑ ∧ A↑

Bu ne demek?
  - R↑: Etki alanı görece yüksek (çok uygulamaya ulaşıyor)
  - A↑: Yoğunlaştırma görece yüksek (az kanal ile ulaşıyor)

  İkisinin birlikte olması → Hub uygulama tespiti

Sadece R↑ olsa: Belki çok kanalla çok uygulamaya ulaşıyor (normal)
Sadece A↑ olsa: Belki az uygulamaya ulaşıyor ama verimli (normal)
İkisi birlikte: Gerçekten kritik merkezi nokta
```

#### 5.2.2. Konu Düzeyi Örüntüler

| Örüntü | Koşul | Anlam |
|--------|-------|-------|
| **İletişim Omurgası (CB)** | $C(t)\!\uparrow \land I(t)\!\downarrow$ | Yüksek kapsayıcılık, dengeli dağılım — çekirdek kanal |
| **Yönlü Yoğunlaşma (DC)** | $I(t)\!\uparrow$ | Tek yönlü kanal (broadcast veya collector) |

**İletişim Omurgası (Communication Backbone) Detaylı Açıklama:**

```
CB örüntüsü: C↑ ∧ I↓

Bu ne demek?
  - C↑: Kapsayıcılık yüksek (çok uygulama bu konuyu kullanıyor)
  - I↓: Dengesizlik düşük (hem yayıncı hem abone var, dengeli)

  İkisinin birlikte olması → Sistemin omurgası olan çekirdek kanal

Sadece C↑ olsa: Belki tek yönlü broadcast kanalı
Sadece I↓ olsa: Belki az kullanılan ama dengeli kanal
İkisi birlikte: Gerçekten sistemin temel haberleşme omurgası
```

#### 5.2.3. Çalışma Düğümü Düzeyi Örüntüler

| Örüntü | Koşul | Anlam |
|--------|-------|-------|
| **Yoğunlaşmış Etkileşim Kümesi (IH)** | $ND(n)\!\uparrow \land NID(n)\!\uparrow$ | Hem yoğun yerleşim hem yoğun iletişim — hotspot |

#### 5.2.4. Kütüphane Düzeyi Örüntüler

| Örüntü | Koşul | Anlam |
|--------|-------|-------|
| **Yaygın Ortak Kütüphane (WUL)** | $LC(l)\!\uparrow$ | Çok uygulama tarafından kullanılıyor |
| **Yoğunlaşmış Ortak Kütüphane (CL)** | $LCon(l)\!\uparrow$ | Belirli düğümlerde yoğunlaşmış kullanım |

---

## 6. Birleşik Aykırılık Skoru

### 6.1. Skor Yapısı

Birleşik aykırılık skoru iki bileşenden oluşur:

```
┌────────────────────────────────────────────────────────────────┐
│              BİRLEŞİK AYKIRLIK SKORU                           │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   Score(x) = OS^P(x) + λ · UNI(x)                             │
│                                                                │
│   ┌─────────────────────┐    ┌─────────────────────┐          │
│   │    OS^P (Örüntü     │    │    UNI (Tek-Boyutlu │          │
│   │    Tabanlı Skor)    │    │    Aykırılık Katkısı)│          │
│   │                     │    │                     │          │
│   │  Çok boyutlu        │    │  Tekil metriklerde  │          │
│   │  yapısal            │    │  aşırı uç durumlar  │          │
│   │  yoğunlaşmalar      │    │  için sınırlı katkı │          │
│   └─────────────────────┘    └─────────────────────┘          │
│              │                          │                      │
│              │         λ küçük          │                      │
│              └──────────┬───────────────┘                      │
│                         ▼                                      │
│                   Nihai Skor                                   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 6.2. Örüntü Tabanlı Aykırılık Skoru (OS^P)

**Formül (Uygulama düzeyi için):**
$$OS^{P}_{\mathcal{A}}(a) = \sum_{p \in \mathcal{P}_{\mathcal{A}}} \frac{1}{|\{a' \in \mathcal{A} \mid p(a')\}|} \cdot \mathbb{I}[p(a)]$$

**Bu formül ne buluyor?**

Bir bileşenin tetiklediği her örüntü için, o örüntünün sistem genelindeki **nadirliğine** göre ağırlıklandırılmış toplam skor hesaplar.

**Detaylı Açıklama:**

1. **$\mathcal{P}_{\mathcal{A}} = \{WR, RS, CS, SD\}$**: Uygulama düzeyi örüntüler kümesi
2. **$\mathbb{I}[p(a)]$**: Iverson bracket — örüntü $p$ uygulama $a$ için sağlanıyorsa 1, değilse 0
3. **Normalizasyon terimi $\frac{1}{|\{a' \mid p(a')\}|}$**: Örüntüyü tetikleyen toplam uygulama sayısının tersi

**Normalizasyonun Amacı:**

```
Senaryo: 100 uygulamalı sistem

Örüntü WR: 2 uygulama tetikliyor → Katkı: 1/2 = 0.5
Örüntü RS: 50 uygulama tetikliyor → Katkı: 1/50 = 0.02

Nadir örüntüler daha yüksek skor katkısı yapar.
Bu, yaygın örüntülerin sıralamayı domine etmesini engeller.
```

**Örnek Hesaplama:**

```
Sistem: 5 uygulama (A0-A4)

Örüntü tetiklenme durumu:
  WR: {A0}        → 1 uygulama → ağırlık = 1/1 = 1.0
  RS: {A0, A1}    → 2 uygulama → ağırlık = 1/2 = 0.5
  CS: {A0, A2}    → 2 uygulama → ağırlık = 1/2 = 0.5
  SD: {}          → 0 uygulama → ağırlık = yok

A0 için OS^P:
  WR tetikleniyor → 1.0 × 1 = 1.0
  RS tetikleniyor → 0.5 × 1 = 0.5
  CS tetikleniyor → 0.5 × 1 = 0.5
  SD tetiklenmiyor → 0
  
  OS^P(A0) = 1.0 + 0.5 + 0.5 = 2.0
```

### 6.3. Tek-Boyutlu Aykırılık Katkısı (UNI)

**Üst kuyruk tabanlı uçluk değeri:**
$$u_M(x) = \begin{cases} 0 & \text{if } M(x) \leq Q_3 \\ \frac{M(x) - Q_3}{M_{max} - Q_3} & \text{if } M(x) > Q_3 \end{cases}$$

**Sınırlandırılmış katkı:**
$$c_M(x) = \min(u_M(x), \tau)$$

**Toplam tek-boyutlu katkı:**
$$UNI(x) = \sum_{M \in \mathcal{M}_x} c_M(x)$$

**Bu formül ne buluyor?**

Tekil metriklerde görülen aşırı uç değerlerin, **sınırlı** bir katkı olarak nihai skora yansımasını sağlar.

**Detaylı Açıklama:**

1. **$u_M(x)$**: Metrik değerinin Q3'ün üzerindeki kısımdaki göreli konumu (0 ile 1 arası)
2. **$\tau$ (TAU)**: Üst sınır (örn. 0.30) — tekil metriğin maksimum katkısı
3. **$\lambda$ (LAMBDA)**: UNI'nin toplam skora katkı ağırlığı (örn. 0.30)

**Neden sınırlama?**

```
PROBLEM: Tekil metrik domine etmesi
  A0: Sadece R metriği çok yüksek, diğer metrikler normal
  A1: Birden fazla metrikte görece yüksek, örüntü tetikliyor

  Sınırlama olmadan: A0 sıralamada öne geçebilir
  Sınırlama ile: A1 daha üstte çünkü çok boyutlu aykırılık gösteriyor
```

**Örnek Hesaplama:**

```
Metrik R için:
  Q3(R) = 5
  max(R) = 10
  
  A0: R(A0) = 8
  u_R(A0) = (8 - 5) / (10 - 5) = 3/5 = 0.6
  c_R(A0) = min(0.6, 0.30) = 0.30  (τ ile sınırlandı)
  
  A1: R(A1) = 6
  u_R(A1) = (6 - 5) / (10 - 5) = 1/5 = 0.2
  c_R(A1) = min(0.2, 0.30) = 0.20
```

### 6.4. Nihai Skor

**Formül:**
$$Score(x) = OS^{P}(x) + \lambda \cdot UNI(x)$$

**Parametreler:**
- **τ (TAU) = 0.30**: Tekil metrik katkı üst sınırı
- **λ (LAMBDA) = 0.30**: UNI ağırlık katsayısı

**Skor Yorumlama:**

```
┌────────────────────────────────────────────────────────────────┐
│                     SKOR YORUMLAMA                             │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Yüksek Score = Yüksek öncelik ile incelenmeli                │
│                                                                │
│  Skor oluşumu:                                                 │
│  • OS^P yüksek → Birden fazla yapısal örüntü tetiklenmiş      │
│  • UNI yüksek → Tekil metriklerde aşırı uç değerler var       │
│                                                                │
│  NOT: Yüksek skor ≠ Hata/Kusur                                │
│       Yüksek skor = "Yapısal olarak dikkat çekici"            │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. Dataset Senaryoları ve Beklenen Davranışlar

Bu bölümde, farklı yapısal senaryoları temsil eden test datasetleri ve modelin bu senaryolarda nasıl davranması gerektiği açıklanmaktadır.

### 7.1. Senaryo 1: Hub Uygulama (hub_application.json)

**Senaryo Açıklaması:**

Tek bir uygulama (A0), birden fazla farklı kategorideki konuya yayın yaparak sistemin merkezinde yer almaktadır.

```
         ┌─────────────────────────────────────────┐
         │              HUB UYGULAMA               │
         └─────────────────────────────────────────┘

                    ┌───────────┐
             ┌─────►│ T0 (nav)  │◄───── A1
             │      └───────────┘
             │      ┌───────────┐
     A0 ─────┼─────►│ T1 (nav)  │◄───── A3
    (HUB)    │      └───────────┘
             │      ┌───────────┐
             ├─────►│ T2 (sensor)│◄───── A2
             │      └───────────┘
             │      ┌───────────┐
             └─────►│ T4 (weapons)│◄───── A4
                    └───────────┘
```

**Dataset Yapısı:**
- 5 uygulama: A0 (hub), A1-A4 (peripheral)
- 5 konu: Farklı kategorilerde (nav, sensor, weapons)
- A0: 4 konuya yayın (nav.track.update, nav.track.delete, sensor.fusion.raw, weapons.control.fire)
- Diğer uygulamalar: Her biri 1 konuya abone

**Beklenen Model Davranışı:**

| Bileşen | Beklenen Sonuç | Sebep |
|---------|----------------|-------|
| **A0** | En yüksek skor | R↑ (4 uygulamaya ulaşıyor), A↑ (4 kanal ile), TC↑ (3 farklı kategori: nav, sensor, weapons) |
| **A0** | WR örüntüsü | Geniş etki alanı + yüksek yoğunlaştırma |
| **A0** | CS örüntüsü | Bağlam çeşitliliği yüksek |
| **A0** | RS örüntüsü | Sadece yayıncı (RA > 0) |
| **A1-A4** | Düşük skor | Sadece 1 konuya abone, tek kategori |

**Doğrulama Kriterleri:**
```
✓ A0.Score > A1.Score, A2.Score, A3.Score, A4.Score
✓ A0.WR = True
✓ A0.CS = True  
✓ A0.RS = True (sadece yayıncı)
✓ A1-A4 için WR = False
```

---

### 7.2. Senaryo 2: Tek İletişim Omurgası (single_backbone_topic.json)

**Senaryo Açıklaması:**

Tek bir konu (T0), sistemdeki tüm uygulamalar tarafından hem yayın hem abonelik için kullanılarak omurga rolü üstlenmektedir.

```
         ┌─────────────────────────────────────────┐
         │          İLETİŞİM OMURGASI              │
         └─────────────────────────────────────────┘

              Yayıncılar          Aboneler
              ┌───────┐          ┌───────┐
              │  A0   │          │  A1   │
              │  A1   │──────────│  A2   │
              │  A2   │──► T0 ───│  A3   │
              │  A3   │          │  A4   │
              └───────┘          └───────┘
```

**Dataset Yapısı:**
- 5 uygulama: A0-A4
- 5 konu: T0 (core.sync.update) + T1-T4 (aux.log.*)
- T0: 4 yayıncı (A0-A3), 4 abone (A1-A4)
- T1-T4: Kullanılmıyor (log kategorisi)

**Beklenen Model Davranışı:**

| Bileşen | Beklenen Sonuç | Sebep |
|---------|----------------|-------|
| **T0** | En yüksek skor | C↑ (8 etkileşim), I↓ (4 yayıncı, 4 abone — dengeli) |
| **T0** | CB örüntüsü | İletişim Omurgası — yüksek kapsayıcılık, düşük dengesizlik |
| **T1-T4** | Düşük skor | C = 0 (kullanılmıyor) |

**Doğrulama Kriterleri:**
```
✓ T0.Score > T1.Score, T2.Score, T3.Score, T4.Score
✓ T0.CB = True
✓ T0.DC = False (dengesizlik düşük)
✓ T0.C = 8 (en yüksek coverage)
✓ T0.I ≈ 0 (dengeli)
```

---

### 7.3. Senaryo 3: Tekil Metrik Aykırısı (single_metric_outlier.json)

**Senaryo Açıklaması:**

Bir uygulama (A0) sadece tek bir metrikte (yayın sayısı) aşırı yüksek değere sahip, diğer metriklerde normal. Bu senaryo, tekil metrik aykırılarının birleşik skoru domine etmemesini test eder.

```
         ┌─────────────────────────────────────────┐
         │       TEKİL METRİK AYKIRISI             │
         └─────────────────────────────────────────┘

              A0 ───publish───► T0 (stream.data.part1)
                 ───publish───► T1 (stream.data.part2)
                 ───publish───► T2 (stream.data.part3)
                 ───publish───► T3 (stream.data.part4)
                 ───publish───► T4 (stream.data.part5)
                 
              (5 konuya yayın, 0 abone, 0 etkileşim)
```

**Dataset Yapısı:**
- 5 uygulama: A0-A4
- 5 konu: Hepsi aynı kategoride (stream.data.*)
- A0: 5 konuya yayın (ama hiçbir abone yok!)
- A1-A4: Hiçbir yayın/abonelik yok

**Beklenen Model Davranışı:**

| Bileşen | Beklenen Sonuç | Sebep |
|---------|----------------|-------|
| **A0** | Orta düzey skor | Y(A0) = 5 ama R(A0) = 0 (kimseye ulaşmıyor) |
| **A0** | RS örüntüsü | RA yüksek (sadece yayıncı) |
| **A0** | WR = False | R düşük (etki alanı yok) |
| **A0** | CS = False | TC = 1 (tek kategori: stream) |
| **A0** | UNI katkısı | RA metriğinde aşırı uç değer |

**Bu Senaryo Ne Test Ediyor?**

```
Problem: A0'ın 5 konuya yayın yapması "etkileyici" görünebilir
Gerçek: Kimse bu konulara abone olmadığı için R = 0

Beklenen Davranış:
  - OS^P düşük (WR ve CS tetiklenmiyor)
  - UNI var ama sınırlı (τ = 0.30 ile)
  - Nihai skor: Çok yüksek değil
  
Bu, modelin "gerçek etkileşimleri" ölçtüğünü gösterir,
sadece "potansiyel kanal sayısını" değil.
```

---

### 7.4. Senaryo 4: Bağlam Çeşitliliği Karşılaştırması (context_diversity_comparison.json)

**Senaryo Açıklaması:**

İki uygulama (A0 ve A1) benzer sayıda kanalda aktif, ancak A0 farklı kategorilerde, A1 tek kategoride.

```
         ┌─────────────────────────────────────────┐
         │     BAĞLAM ÇEŞİTLİLİĞİ KARŞILAŞTIRMASI │
         └─────────────────────────────────────────┘

         A0:                          A1:
         ├─► T0 (nav.track.update)    └─► T1 (nav.track.delete)
         ├─► T2 (sensor.fusion.raw)   
         └─► T3 (weapons.control.arm)
         
         TC(A0) = 3 kategoriler        TC(A1) = 1 kategori
         (nav, sensor, weapons)        (nav)
```

**Dataset Yapısı:**
- 5 uygulama: A0-A4
- 5 konu: Farklı kategorilerde (nav, sensor, weapons, log)
- A0: 3 farklı kategoriye yayın (nav, sensor, weapons)
- A1: 1 kategoriye yayın (nav)
- A2-A4: Her biri 1 konuya abone

**Beklenen Model Davranışı:**

| Bileşen | Beklenen Sonuç | Sebep |
|---------|----------------|-------|
| **A0** | Daha yüksek skor | TC↑ (3 kategori) → CS örüntüsü |
| **A0** | CS = True | Bağlam çeşitliliği görece yüksek |
| **A1** | Daha düşük skor | TC = 1 (tek kategori) |
| **A1** | CS = False | Bağlam çeşitliliği düşük |

**Bu Senaryo Ne Test Ediyor?**

```
LCP tabanlı kategori çıkarımının doğruluğunu test eder:

Konular ve Kategorileri:
  T0: "nav.track.update"    → LCP: "nav" (T1 ile)
  T1: "nav.track.delete"    → LCP: "nav" (T0 ile)
  T2: "sensor.fusion.raw"   → LCP: "sensor" 
  T3: "weapons.control.arm" → LCP: "weapons"
  T4: "log.system.error"    → LCP: "log"

A0 kategorileri: {nav, sensor, weapons} → TC(A0) = 3
A1 kategorileri: {nav}                  → TC(A1) = 1
```

---

### 7.5. Senaryoların Özet Karşılaştırması

| Senaryo | Test Edilen Özellik | Kritik Metrikler | Beklenen Aykırı |
|---------|---------------------|------------------|-----------------|
| Hub Application | Merkezi uygulama tespiti | R, A, TC | A0 (uygulama) |
| Single Backbone | Omurga konu tespiti | C, I | T0 (konu) |
| Single Metric Outlier | Tekil metrik domine etmemesi | RA, UNI | A0 (sınırlı skor) |
| Context Diversity | Bağlam çeşitliliği ayrımı | TC | A0 > A1 |

---

## 8. Bulgular ve Sonuçlar Bölümünün Hazırlanması

### 8.1. Deney Metodolojisi

Bulgular bölümünün sistematik olarak hazırlanması için aşağıdaki adımlar izlenmelidir:

#### Adım 1: Veri Hazırlığı

```
┌──────────────────────────────────────────────────────────────────┐
│                    ADIM 1: VERİ HAZIRLIĞI                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1.1. Statik Analiz Çıktılarının Toplanması                     │
│       • CodeQL sorgu sonuçları                                   │
│       • Yayın/abonelik ilişkileri                               │
│       • Uygulama-düğüm eşleştirmeleri                           │
│       • Kütüphane kullanım bilgileri                            │
│                                                                  │
│  1.2. Çizge Temsilinin Oluşturulması                            │
│       • JSON formatında veri yapılandırması                      │
│       • Düğüm ve kenar listelerinin oluşturulması               │
│       • Konu kategori çıkarımı (LCP algoritması)                │
│                                                                  │
│  1.3. Veri Doğrulaması                                          │
│       • Bütünlük kontrolü (orphan düğümler var mı?)             │
│       • Tutarlılık kontrolü (çift yönlü referanslar)            │
│       • Kapsam kontrolü (tüm bileşenler dahil mi?)              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

#### Adım 2: Metrik Hesaplaması

```
┌──────────────────────────────────────────────────────────────────┐
│                   ADIM 2: METRİK HESAPLAMASI                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  2.1. Uygulama Düzeyi Metrikler                                 │
│       • Her uygulama için: R, A, RA, TC, LE                     │
│       • Toplam: |A| × 5 metrik değeri                           │
│                                                                  │
│  2.2. Konu Düzeyi Metrikler                                     │
│       • Her konu için: C, I, PS                                  │
│       • Toplam: |T| × 3 metrik değeri                           │
│                                                                  │
│  2.3. Çalışma Düğümü Düzeyi Metrikler                           │
│       • Her düğüm için: ND, NID                                  │
│       • Toplam: |N| × 2 metrik değeri                           │
│                                                                  │
│  2.4. Kütüphane Düzeyi Metrikler                                │
│       • Her kütüphane için: LC, LCon                             │
│       • Toplam: |L| × 2 metrik değeri                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

#### Adım 3: İstatistiksel Analiz

```
┌──────────────────────────────────────────────────────────────────┐
│                  ADIM 3: İSTATİSTİKSEL ANALİZ                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  3.1. Dağılım Analizi                                           │
│       • Her metrik için: min, Q1, median, Q3, max               │
│       • Histogram ve kutu grafikleri                             │
│       • Çarpıklık ve basıklık değerleri                         │
│                                                                  │
│  3.2. Göreli Eşik Belirleme                                     │
│       • Q1 ve Q3 değerlerinin hesaplanması                      │
│       • ↑ ve ↓ bayraklarının atanması                           │
│                                                                  │
│  3.3. Korelasyon Analizi                                        │
│       • Metrikler arası korelasyon matrisi                      │
│       • Yüksek korelasyonlu metrik çiftlerinin tespiti          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

#### Adım 4: Örüntü Tespiti ve Skorlama

```
┌──────────────────────────────────────────────────────────────────┐
│              ADIM 4: ÖRÜNTÜ TESPİTİ VE SKORLAMA                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  4.1. Örüntü Değerlendirmesi                                    │
│       • Her bileşen için tanımlı örüntülerin kontrolü           │
│       • Örüntü tetiklenme sayılarının hesaplanması              │
│       • Örüntü başına etkilenen bileşen listesi                 │
│                                                                  │
│  4.2. OS^P Hesaplaması                                          │
│       • Normalizasyon faktörlerinin hesaplanması                │
│       • Bileşen başına örüntü tabanlı skor                      │
│                                                                  │
│  4.3. UNI Hesaplaması                                           │
│       • Üst kuyruk uçluk değerleri                              │
│       • τ ile sınırlandırma                                      │
│                                                                  │
│  4.4. Nihai Skor                                                │
│       • Score = OS^P + λ × UNI                                  │
│       • Bileşen türü bazında sıralama                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

#### Adım 5: Uzman Değerlendirmesi

```
┌──────────────────────────────────────────────────────────────────┐
│                 ADIM 5: UZMAN DEĞERLENDİRMESİ                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  5.1. Değerlendirme Protokolü                                   │
│       • Uzman profili tanımı (deneyim, alan bilgisi)            │
│       • Değerlendirme kriterleri                                │
│       • Körlemeden (blind) değerlendirme prosedürü              │
│                                                                  │
│  5.2. Karşılaştırma Metrikleri                                  │
│       • Top-K örtüşme (Precision@K)                             │
│       • Sıralama korelasyonu (Spearman/Kendall)                 │
│       • Cohen's Kappa (inter-rater agreement)                   │
│                                                                  │
│  5.3. Nitel Değerlendirme                                       │
│       • Her aykırı için uzman yorumu                            │
│       • Yanlış pozitif/negatif analizi                          │
│       • İyileştirme önerileri                                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2. Sonuç Raporlama Formatı

#### 8.2.1. Sistem Genel Bakış Tablosu

```markdown
| Bileşen Türü | Sayı | Örüntü Tetikleyen | Oran |
|--------------|------|-------------------|------|
| Uygulama     | 150  | 23                | %15  |
| Konu         | 320  | 18                | %6   |
| Düğüm        | 12   | 3                 | %25  |
| Kütüphane    | 45   | 7                 | %16  |
```

#### 8.2.2. Metrik Dağılım Tablosu

```markdown
| Metrik | Min | Q1  | Median | Q3  | Max | Std  |
|--------|-----|-----|--------|-----|-----|------|
| R      | 0   | 2   | 5      | 12  | 45  | 8.3  |
| A      | 0   | 0.5 | 1.2    | 3.5 | 15  | 2.8  |
| RA     |-0.8 |-0.2 | 0.1    | 0.3 | 0.9 | 0.35 |
| ...    | ... | ... | ...    | ... | ... | ...  |
```

#### 8.2.3. Top Aykırılar Tablosu

```markdown
| Sıra | ID  | Score | OS^P | UNI  | Örüntüler    | Uzman Görüşü |
|------|-----|-------|------|------|--------------|--------------|
| 1    | A23 | 2.85  | 2.50 | 1.17 | WR, CS, RS   | Doğrulandı   |
| 2    | A07 | 2.12  | 1.75 | 1.23 | WR, SD       | Doğrulandı   |
| 3    | A45 | 1.95  | 1.50 | 1.50 | CS, SD       | Kısmen       |
| ...  | ... | ...   | ...  | ...  | ...          | ...          |
```

#### 8.2.4. Örüntü Bazlı Bulgular

Her örüntü için ayrı bir alt bölüm hazırlanmalıdır:

```markdown
### Geniş Etki Alanı (Wide Reach) Bulguları

**Tetiklenen Bileşen Sayısı:** 8 uygulama (toplam 150'den)

**En Yüksek Skorlu 3 Uygulama:**

1. **A23 (Sensör Füzyon Yöneticisi)**
   - R = 45, A = 15, TC = 8
   - 12 farklı uygulamaya 3 kanal üzerinden ulaşıyor
   - Uzman Değerlendirmesi: "Sistemin kritik entegrasyon noktası"

2. **A07 (Veri Dağıtım Servisi)**
   - R = 38, A = 12.7, TC = 6
   - Tüm sensör verilerini ilgili modüllere dağıtıyor
   - Uzman Değerlendirmesi: "Beklenen davranış, mimari tasarım gereği"
   
[...]
```

### 8.3. Tehditler ve Sınırlılıklar

Bulgular bölümünde aşağıdaki tehditler tartışılmalıdır:

```
┌──────────────────────────────────────────────────────────────────┐
│                   TEHDİTLER VE SINIRLILIKLAR                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. İç Geçerlilik Tehditleri                                    │
│     • Statik analizin tüm çağrıları yakalayamaması              │
│     • Reflection ve dinamik çağrıların dışarıda kalması         │
│     • Polimorfizm çözümlemesinin yaklaşıklığı                   │
│                                                                  │
│  2. Dış Geçerlilik Tehditleri                                   │
│     • Tek sistem üzerinde değerlendirme                         │
│     • Java dışı diller için uygulanabilirlik                    │
│     • Farklı pub/sub çerçeveleri                                │
│                                                                  │
│  3. Yapı Geçerliliği Tehditleri                                 │
│     • Uzman değerlendirmelerinin öznel olması                   │
│     • Q1/Q3 eşiklerinin evrenselliği                            │
│     • λ ve τ parametrelerinin kalibrasyonu                      │
│                                                                  │
│  4. Sonuç Geçerliliği Tehditleri                                │
│     • Örnek boyutunun yeterliliği                               │
│     • Aykırılık kavramının göreceliliği                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 8.4. Örnek Bulgular Metni

```markdown
## 5. Bulgular ve Değerlendirme

### 5.1. Genel Sistem Karakteristiği

ADVENT sistemi üzerinde gerçekleştirilen statik analiz sonucunda,
toplam 150 uygulama, 320 konu, 12 çalışma düğümü ve 45 ortak
kütüphane tespit edilmiştir. Sistemde 2,847 yayınlama ve 3,124
abonelik ilişkisi belirlenmiştir.

### 5.2. Uygulama Düzeyi Bulgular

Uygulama düzeyinde tanımlanan dört yapısal örüntüden en az birini
tetikleyen 23 uygulama (%15) belirlenmiştir. Bu uygulamaların
dağılımı Tablo 1'de sunulmaktadır.

[Tablo 1: Uygulama Düzeyi Örüntü Dağılımı]

En yüksek birleşik aykırılık skoruna sahip beş uygulama incelendiğinde,
bunların büyük çoğunluğunun (%80) alan uzmanları tarafından da "mimari
açıdan kritik" veya "dikkat gerektiren" olarak değerlendirildiği
görülmektedir.

### 5.3. Konu Düzeyi Bulgular

İletişim Omurgası (CB) örüntüsünü tetikleyen 5 konu belirlenmiştir.
Bu konuların sistemin temel veri dağıtım mekanizmalarını oluşturduğu
ve değişiklik durumunda geniş etki alanına sahip olacağı uzman
değerlendirmeleriyle doğrulanmıştır.

[...]
```

---

## Test Senaryoları ve Beklenen Sonuçlar

### Senaryo 1: Hub Application (`hub_application.json`)

**Yapı:**
- A0: 6 topic'e publish (T0, T1, T3, T4, T6, T8), 3 kütüphane (L0, L1, L2)
- Bu topic'lere toplam 12 farklı uygulama subscribe ediyor
- Diğer uygulamalar 1-2 topic ile sınırlı

**Beklenen Sonuçlar:**
| Varlık | Beklenen Örüntüler | Açıklama |
|--------|-------------------|----------|
| A0 | WR=True, RS=True, CS=True, SD=True | En yüksek R, yayıncı ağırlıklı, 5 kategori, 3 lib |
| A0 | En yüksek Score | Hub uygulama olarak öne çıkmalı |

---

### Senaryo 2: Single Backbone Topic (`single_backbone_topic.json`)

**Yapı:**
- T0 ("core.sync.state"): 8 publisher, 8 subscriber — sistemin omurgası
- T1, T2, T5, T7: 1 publisher, 1 subscriber — küçük ama dengeli
- T3, T4, T6, T8: sadece publisher, subscriber yok — tek yönlü

**Beklenen Sonuçlar:**
| Varlık | Beklenen Örüntüler | Açıklama |
|--------|-------------------|----------|
| T0 | CB=True | C=16 (en yüksek), I=0 (dengeli: 8=8) |
| T0 | En yüksek Score | İletişim omurgası |
| T1,T2,T5,T7 | CB=True | C=2 >= Q3, I=0 (dengeli: 1=1) |
| T3,T4,T6,T8 | CB=False | C=1 < Q3 veya I=0.5 > Q1 |

**Not:** CB örüntüsü "yüksek bağlantı + düşük dengesizlik" arar. Küçük ama dengeli
topic'ler de bu şartı sağlayabilir. T0'ı diğerlerinden ayıran şey **Score** değeri.

---

### Senaryo 3: Single Metric Outlier (`single_metric_outlier.json`)

**Yapı:**
- A0: 8 topic'e publish (T0-T7), 0 subscribe — saf yayıncı
- AMA bu 8 topic'e kimse subscribe değil! R(A0) = 0
- A1: T8, T9'a publish, T10'a subscribe — kontrol uygulaması

**Beklenen Sonuçlar:**
| Varlık | Beklenen Örüntüler | Açıklama |
|--------|-------------------|----------|
| A0 | RS=True | RA↑ (saf yayıncı, sadece publish) |
| A0 | WR=False | R=0, kimseye ulaşmıyor |
| A0 | En yüksek Score DEĞİL | Tek metrik aykırılığı sınırlı etki |

---

### Senaryo 4: Context Diversity Comparison (`context_diversity_comparison.json`)

**Yapı:**
- A0: 5 kategoride topic (nav, sensor, weapons, comms, log) — çeşitli
- A1: 2 kategoride topic (nav, log) — sınırlı
- Her ikisi de birden fazla topic kullanıyor ama bağlam farklı

**Beklenen Sonuçlar:**
| Varlık | Beklenen Örüntüler | Açıklama |
|--------|-------------------|----------|
| A0 | CS=True | TC↑ (5 farklı kategori) |
| A0.TC > A1.TC | Karşılaştırma | 5 > 2 |

---

## Sonuç

Bu dokümantasyon, yayınla–abone ol tabanlı dağıtık sistemlerde yapısal etkileşim örüntülerinin çizge tabanlı statik analizi için kapsamlı bir metodoloji sunmaktadır. Tanımlanan metrikler, örüntüler ve skorlama mekanizması, mimari değerlendirme süreçlerini destekleyen yapısal sinyaller üretmeyi amaçlamaktadır.

Yaklaşımın temel güçlü yönleri:
- **Çalışma zamanı bağımsızlığı:** Statik analiz ile tüm kod tabanı kapsanır
- **Göreli değerlendirme:** Sistem bağlamına duyarlı eşikler
- **Çok boyutlu analiz:** Tek metrik yerine örüntü tabanlı yaklaşım
- **Açıklanabilirlik:** Her skor bileşeni izlenebilir

Gelecek çalışmalarda, bu yaklaşımın farklı sistemler üzerinde değerlendirilmesi ve makine öğrenmesi yöntemleriyle zenginleştirilmesi hedeflenmektedir.
