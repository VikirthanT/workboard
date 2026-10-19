import { expect, it } from 'vitest';
import { slugify } from './slug';

it('makes a readable team slug', () => expect(slugify(' NPI  Team! ')).toBe('npi-team'));
