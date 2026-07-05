"""KI-Layer (ADR 004) – vier dünne Schichten:

``gateway``    provider-agnostischer Zugang zu Claude (Vertex-EU/direkt) + Gemini-Bild
``identity``   die KI als echter Principal (System-``UserProfile``, ``role='ai'``)
``principal``  Delegation: KI handelt mit den EFFEKTIVEN Rechten des Nutzers
``tools``      rechte-gescopte Tools – Wrapper um die BESTEHENDEN autorisierten Services
``assistant``  Chat-Orchestrierung (Tool-Use-Loop, Grounding auf echten Daten)
``actions``    Vorschlag → menschliche Bestätigung → autorisierter Pfad (kritische Aktionen)

Sicherheitsgrenze ist die Authz der Service-Schicht, NIE der Prompt."""
