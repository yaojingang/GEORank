import type {
  AdminCompanyCreatePayload,
  AdminCompanyUpdatePayload
} from '@georank/api-sdk';

const createPayload: AdminCompanyCreatePayload = {
  name: 'Example',
  url: 'https://example.com'
};

const updatePayload: AdminCompanyUpdatePayload = {
  description: 'Updated description'
};

// @ts-expect-error create payloads require a company name.
const missingName: AdminCompanyCreatePayload = {url: 'https://example.com'};

// @ts-expect-error create payloads require a company URL.
const missingUrl: AdminCompanyCreatePayload = {name: 'Example'};

void createPayload;
void updatePayload;
void missingName;
void missingUrl;
