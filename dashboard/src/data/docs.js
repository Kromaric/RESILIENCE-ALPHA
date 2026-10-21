export const sections = [
  {
    title: 'Démarrage',
    pages: [
      { slug: 'readme', title: 'README et déploiement' },
      { slug: 'compose', title: 'Docker Compose' },
      { slug: 'vault', title: 'Secrets avec Vault' },
    ],
  },
  {
    title: 'Architecture',
    pages: [
      { slug: 'overview', title: "Vue d'ensemble" },
      { slug: 'flux', title: 'Flux de paiement' },
      { slug: 'reseau', title: 'Réseau 192.168.137.0/24' },
    ],
  },
  {
    title: 'Exploitation',
    pages: [
      { slug: 'runbook-payment', title: 'Runbook remédiation payment-api' },
      { slug: 'playbooks', title: 'Playbooks Ansible' },
      { slug: 'observabilite', title: 'Observabilité' },
    ],
  },
  {
    title: 'IA / Data',
    pages: [
      { slug: 'aiops', title: 'Modèle de détection AIOps' },
      { slug: 'rag', title: 'Assistant RAG' },
    ],
  },
  {
    title: 'Cybersécurité',
    pages: [
      { slug: 'waf', title: 'WAF' },
      { slug: 'siem', title: 'SIEM' },
      { slug: 'durcissement', title: 'Durcissement' },
    ],
  },
  {
    title: 'Gouvernance',
    pages: [
      { slug: 'ebios', title: 'EBIOS RM' },
      { slug: 'pca', title: 'PCA / PRA' },
      { slug: 'nis2', title: 'NIS2 / DORA' },
    ],
  },
]

export const runbookToc = [
  { id: 'declencheurs', title: '1. Déclencheurs' },
  { id: 'sequence', title: '2. Séquence automatique' },
  { id: 'playbook', title: '3. Playbook appelé' },
  { id: 'reprise', title: '4. Critères de reprise' },
  { id: 'escalade', title: '5. Escalade manuelle' },
]

export const playbook = `- name: Remédiation payment-api
  hosts: pc_hote
  tasks:
    - name: Limiter le débit de la source suspecte
      uri: { url: "http://waf:8080/rules/rate-limit", method: POST }
    - name: Redémarrer le service de façon contrôlée
      community.docker.docker_compose_v2:
        project_src: /opt/orbe
        services: [payment-api]
        state: restarted
    - name: Attendre le healthcheck
      uri: { url: "http://payment-api:8000/health", status_code: 200 }
      retries: 12
      delay: 5`