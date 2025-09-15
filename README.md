# RSPS Color Bot v3

Een geavanceerde color bot voor RuneScape Private Servers met verbeterde detectie, configuratie en gebruikersinterface.

## Korte update (2025-09-15)

- Tijdinstellingen kregen fijnere precisie en ruimere bereiktes (Combat, Detection, Potion, Instance) met duidelijke "s"-suffix en tooltips.
- Overlay toont nu "Wait: X.Xs" tijdens de post-combat wachttijd; deze resterende tijd is ook beschikbaar als `post_combat_remaining_s` in detectieresultaten.
- Profielen opslaan is robuuster: actieve invoervelden worden eerst gefinaliseerd zodat bewerkingen niet verloren gaan.
- Betere betrouwbaarheid: keep-awake hulpprogramma geïntegreerd en een capture-test modus om snel de scherm-capture te valideren.

## Kenmerken

- **Verbeterde Detectie Engine**: Snellere en nauwkeurigere kleurdetectie met optimalisaties voor prestaties
- **Modulaire Architectuur**: Duidelijk gescheiden componenten voor betere onderhoudbaarheid
- **Geavanceerde Configuratie**: Uitgebreide validatie en typering van configuratie-instellingen
- **Event Systeem**: Flexibel event-gebaseerd systeem voor communicatie tussen componenten
- **State Machine**: Robuuste state machine voor het beheren van bot gedrag
- **Verbeterde GUI**: Moderne, tab-gebaseerde interface met uitgebreide instellingen
- **Uitgebreide Logging**: Gedetailleerde logging met niveaufiltering en opslag
- **Profiel Systeem**: Opslaan en laden van configuratieprofielen
- **Geavanceerde Humanisatie**: Uitgebreide humanisatie van muis- en toetsenbordacties met fatigue-simulatie
- **Parallelle Verwerking**: Verbeterde prestaties door parallelle verwerking van detectietaken
- **Machine Learning Detectie**: Geavanceerde objectdetectie met machine learning
- **Adaptieve Detectie**: Zelfaanpassende detectiealgoritmen voor verschillende omgevingen

## Nieuwe Functies

### Parallelle Verwerking

De bot maakt nu gebruik van parallelle verwerking voor kleurdetectie, wat resulteert in aanzienlijke prestatieverbeteringen:

- **Thread Pool**: Efficiënt beheer van worker threads voor parallelle taken
- **Regio-gebaseerde Verwerking**: Verdeelt het scherm in regio's voor parallelle analyse
- **Schaalbare Prestaties**: Past zich automatisch aan aan het aantal beschikbare CPU-cores
- **Taak Prioritering**: Prioriteert belangrijke detectietaken voor optimale responsiviteit

### Machine Learning Detectie

De bot ondersteunt nu machine learning-gebaseerde objectdetectie:

- **Meerdere Model Formaten**: Ondersteuning voor YOLO, TensorFlow en ONNX modellen
- **Trainingstools**: Tools voor het verzamelen van trainingsdata en het trainen van modellen
- **Hybride Detectie**: Combineert traditionele kleurdetectie met ML-detectie voor optimale resultaten
- **Visualisatie**: Visualisatie van detectieresultaten voor debugging en analyse

### Geavanceerde Humanisatie

De bot bevat nu een uitgebreid humanisatiesysteem voor natuurlijkere interacties:

- **Fatigue Simulatie**: Simuleert menselijke vermoeidheid tijdens langere sessies
- **Persoonlijkheidsprofielen**: Consistente gedragspatronen voor muis en toetsenbord
- **Contextbewuste Acties**: Aanpassing van timing en gedrag op basis van context
- **Natuurlijke Bewegingspatronen**: Geavanceerde Bezier-curves met micro-afwijkingen
- **Realistische Typpatronen**: Menselijke typfouten en correctiegedrag

### Adaptieve Detectie

De bot bevat nu adaptieve detectiealgoritmen die zich aanpassen aan verschillende omgevingen:

- **Omgevingsdetectie**: Automatische detectie van lichtomstandigheden en kleurschema's
- **Parameter Optimalisatie**: Zelflerend systeem voor optimale detectieparameters
- **Foutherstellingsmechanismen**: Geavanceerde strategieën voor herstel bij detectiefouten
- **Persistente Leerervaring**: Bewaart geleerde parameters tussen sessies
- **Omgevingsvisualisatie**: Tools voor het visualiseren van omgevingsanalyse

## Installatie

### Vereisten

- Python 3.8 of hoger
- Pip (Python package manager)

### Stappen

1. Clone de repository:

   ```bash
   git clone https://github.com/yourusername/RSPS-color-bot-v3.git
   cd RSPS-color-bot-v3
   ```

2. Installeer de benodigde packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Start de applicatie:

   ```bash
   python run.py
   ```

## Gebruik

### Basis Configuratie

1. Start de applicatie
2. Ga naar het "Main" tabblad
3. Selecteer het RuneScape venster in de dropdown
4. Klik op "Focus" om het venster te activeren
5. Configureer de detectie-instellingen in het "Detection Settings" tabblad
6. Configureer de combat-instellingen in het "Combat Settings" tabblad

### Profielen

1. Ga naar het "Profiles" tabblad
2. Klik op "Save As" om de huidige configuratie op te slaan
3. Geef een naam voor het profiel
4. Gebruik "Load" om een opgeslagen profiel te laden

### Humanisatie Instellingen

1. Ga naar het "Humanization" tabblad
2. Kies een voorgedefinieerd persoonlijkheidsprofiel of pas individuele instellingen aan
3. Stel vermoeidheidssimulatie in voor langere sessies
4. Configureer contextspecifieke gedragspatronen

### Adaptieve Detectie Instellingen

1. Ga naar het "Adaptive Detection" tabblad
2. Schakel adaptieve detectie in
3. Configureer leersnelheid en exploratiegraad
4. Bekijk omgevingsanalyse en aanbevolen parameters

### Bot Starten

1. Configureer alle instellingen
2. Klik op de "Start" knop in de hoofdinterface
3. De bot zal beginnen met het detecteren en klikken op monsters

## Parallelle Verwerking Testen

Test de prestatieverbetering van parallelle verwerking:

```bash
python benchmark_parallel_detection.py
```

Dit script zal de prestaties van de parallelle detector vergelijken met de originele detector en de resultaten visualiseren.

## Machine Learning Detectie (Overzicht)

### Data Verzamelen

Verzamel trainingsdata voor de ML detector:

```bash
python data_collection_tool.py
```

Dit tool helpt bij het verzamelen en annoteren van trainingsdata voor de ML detector.

### Model Trainen

Train een ML model met de verzamelde data:

```bash
python train_ml_model.py
```

Dit script traint een YOLO model met de verzamelde data en exporteert het naar ONNX formaat voor snellere inferentie.

### ML Detectie Testen

Test de ML detector en parallelle verwerking:

```bash
python test_ml_parallel.py
```

Dit script demonstreert de ML detector en parallelle verwerking in actie.

## Geavanceerde Humanisatie Testen

Test de geavanceerde humanisatiefuncties:

```bash
python test_enhanced_humanization.py
```

Dit script biedt een interactieve demo van de geavanceerde humanisatiefuncties, inclusief visualisatie van muisbewegingen, typpatronen en vermoeidheidseffecten.

## Adaptieve Detectie Testen

Test de adaptieve detectiefuncties:

```bash
python test_enhanced_adaptive_detection.py
```

Dit script demonstreert de adaptieve detectiefuncties, inclusief omgevingsanalyse, parameteraanpassing en foutherstel.

## Architectuur

De bot is opgebouwd uit de volgende hoofdcomponenten:

- **ConfigManager**: Beheert configuratie-instellingen en profielen
- **EventSystem**: Faciliteert communicatie tussen componenten
- **BotController**: Beheert de hoofdstatus van de bot
- **StateMachine**: Beheert de gedragsstatus van de bot
- **DetectionEngine**: Coördineert detectie van tegels, monsters en combat status
- **ParallelDetector**: Implementeert parallelle verwerking voor verbeterde prestaties
- **MLDetector**: Implementeert machine learning-gebaseerde objectdetectie
- **EnhancedAdaptiveDetector**: Implementeert adaptieve detectiealgoritmen
- **ActionManager**: Beheert acties zoals muisklikken en toetsaanslagen
- **EnhancedHumanizedMouse**: Implementeert geavanceerde muishumanisatie
- **EnhancedHumanizedKeyboard**: Implementeert geavanceerde toetsenbordhumanisatie
- **EnhancedActionSequence**: Coördineert complexe actiesequenties met humanisatie
- **GUI**: Biedt een gebruikersinterface voor configuratie en monitoring

## Bijdragen

Bijdragen zijn welkom! Volg deze stappen om bij te dragen:

1. Fork de repository
2. Maak een feature branch (`git checkout -b feature/amazing-feature`)
3. Commit je wijzigingen (`git commit -m 'Add some amazing feature'`)
4. Push naar de branch (`git push origin feature/amazing-feature`)
5. Open een Pull Request

## Licentie

Dit project is gelicenseerd onder de MIT License - zie het LICENSE bestand voor details.

## Disclaimer

Deze bot is alleen bedoeld voor educatieve doeleinden en voor gebruik op private servers waar botting is toegestaan. Gebruik op officiële RuneScape servers is tegen de regels en kan leiden tot een ban.