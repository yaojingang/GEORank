import type { CompanyDetail } from '@georank/api-sdk';

export function asStringList(values: unknown[] | undefined): string[] {
  return (values || [])
    .map((item) => String(item).trim())
    .filter(Boolean);
}

export function formatCompanyDate(value?: string | null) {
  if (!value) return '--';
  return value.replace(/-/g, '/');
}

type CompanySignalLabels = {
  technicalSemantic: string;
  regionalSignal: string;
  teamSignal: string;
  topicCoverage: string;
  notProvided: string;
  needsEnhancement: string;
  publicEntities: (count: number) => string;
  semanticTagCount: (count: number) => string;
};

export function getCompanyOverview(company: CompanyDetail, fallback: string) {
  return (
    company.short_description ||
    company.description ||
    fallback
  );
}

export function normalizeGeoDetails(company: CompanyDetail) {
  const raw = (company.geo_details || {}) as Record<string, unknown>;
  const keys = ['schema', 'content', 'meta', 'citation'];

  return keys.map((key) => {
    const value = Number(raw[key] ?? 0);
    return {
      key,
      label:
        key === 'schema'
          ? 'Schema'
          : key === 'content'
            ? 'Content'
            : key === 'meta'
              ? 'Meta'
              : 'Citation',
      value: Number.isFinite(value) ? value : 0
    };
  });
}

export function deriveCompanySignals(company: CompanyDetail, labels: CompanySignalLabels) {
  const tags = asStringList(company.tags);
  const techStack = asStringList(company.tech_stack);
  const teamMembers = asStringList(company.team_members);

  return [
    {
      label: labels.technicalSemantic,
      value: techStack.length ? techStack.slice(0, 2).join(' / ') : labels.notProvided,
      accent: techStack.length ? 'is-strong' : ''
    },
    {
      label: labels.regionalSignal,
      value: company.headquarters || labels.notProvided,
      accent: company.headquarters ? 'is-strong' : ''
    },
    {
      label: labels.teamSignal,
      value: teamMembers.length ? labels.publicEntities(teamMembers.length) : labels.needsEnhancement,
      accent: teamMembers.length ? 'is-strong' : 'is-warning'
    },
    {
      label: labels.topicCoverage,
      value: labels.semanticTagCount(tags.length || 0),
      accent: tags.length ? 'is-strong' : ''
    }
  ];
}
