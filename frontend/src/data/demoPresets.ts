export interface DemoPreset {
  id: string;
  name: string;
  filename: string;
  description: string;
  category: 'demo' | 'samples';
  kind: 'transcript' | 'audio';
  content?: string;
}

export const DEMO_PRESETS: DemoPreset[] = [
  {
    id: 'meeting_01_kickoff',
    name: 'Meeting 01: Project Kickoff',
    filename: 'meeting_01_kickoff.txt',
    description: 'Initial stack decisions: React, FastAPI, PostgreSQL & Auth0.',
    category: 'demo',
    kind: 'transcript',
    content: `[TRANSCRIPT — Project Nexus Kickoff Call] [2024-03-04 10:02 AM | Attendees: Sarah Chen (PM), Dev Rao (Eng Lead), Priya Nair (Design), Marcus Webb (Stakeholder)]

Sarah Chen: Let's kick off Project Nexus properly. Marcus, you're here from the client side — good to have you. Dev, can you walk us through the proposed stack?

Dev Rao: Sure. For the frontend, I'd recommend React — it gives us the most flexibility for the interactive dashboard views we've scoped. For the backend, FastAPI — fast to build with, good async support for what we need.

Sarah Chen: Agreed on both. Let's lock those in — use React for the frontend, use FastAPI for the backend.

Dev Rao: For the database, I'm proposing PostgreSQL for primary storage. It's reliable, well-understood, and fits our current relational data model.

Sarah Chen: Let's go with that for now — use PostgreSQL for primary storage.

Priya Nair: On the design side, I'd like us to standardize on Material UI as our component library for V1. It'll save us significant time versus building custom components from scratch.

Sarah Chen: Agreed — use Material UI component library for V1.

Marcus Webb: Before we go further, I need to flag two hard requirements from the client side. First, authentication — we've evaluated a few providers and I want us to commit to Auth0. It's proven, and our security team is comfortable with it.

Sarah Chen: Understood — use Auth0 for authentication.`,
  },
  {
    id: 'meeting_02_sprint3_review',
    name: 'Meeting 02: Sprint 3 Review',
    filename: 'meeting_02_sprint3_review.txt',
    description: 'Database pivot: Supersedes PostgreSQL with MongoDB for evolving schema.',
    category: 'demo',
    kind: 'transcript',
    content: `[TRANSCRIPT — Project Nexus Sprint 3 Review] [2024-04-11 2:15 PM | Attendees: Sarah Chen (PM), Dev Rao (Eng Lead), Priya Nair (Design), Lena Hoffmann (New Backend Engineer)]

Sarah Chen: Welcome Lena — you're joining us on backend starting this sprint, correct?

Lena Hoffmann: That's right, happy to be here. I've spent the last few days going through the current schema and I wanted to raise something before we get too much further in.

Sarah Chen: Go ahead.

Lena Hoffmann: Our data model has been evolving fast — a lot of nested, variable-shape data for project metadata and activity logs. PostgreSQL is workable, but we're fighting the relational schema more than benefiting from it at this point. I'd recommend switching to MongoDB for primary storage — it fits this kind of evolving, document-shaped data much more naturally.

Dev Rao: I've noticed the same friction honestly. What would the migration effort look like?

Lena Hoffmann: Manageable if we do it now rather than later — the dataset's still small. It gets a lot harder the longer we wait.

Sarah Chen: Okay, let's make the call now while it's cheap. Switch to MongoDB for primary storage — this supersedes the PostgreSQL decision from the kickoff.

Dev Rao: Agreed, better to eat this cost now.

Sarah Chen: Lena, can you own putting together the actual migration plan?

Lena Hoffmann: Yes, I'll draft the migration plan this week.`,
  },
  {
    id: 'meeting_03_architecture_review',
    name: 'Meeting 03: Architecture Review',
    filename: 'meeting_03_architecture_review.txt',
    description: 'EU data residency compliance pass & security architecture documentation.',
    category: 'demo',
    kind: 'transcript',
    content: `[TRANSCRIPT — Project Nexus Architecture Review] [2024-05-06 11:00 AM | Attendees: Sarah Chen (PM), Dev Rao (Eng Lead), Lena Hoffmann (Backend), Raj Patel (Security)]

Sarah Chen: Raj, thanks for joining — you'll be leading the security and compliance review ahead of launch, right?

Raj Patel: That's right. Given the EU data residency requirement from the kickoff, I want to do a full pass over the architecture before we get too close to launch. Better to catch anything now than after we ship.

Dev Rao: Makes sense. Happy to walk you through anything you need.

Raj Patel: I'll need a clear picture of the current system architecture — every service, every third-party integration, and where each one actually stores or processes data.

Dev Rao: I can put that together. I'll document the current architecture end to end so you've got a clean reference to review against.

Raj Patel: That would help a lot. Lena, on the MongoDB side — can you walk me through how access control and authentication into the database itself is configured? I want to make sure that's locked down properly before launch too.

Lena Hoffmann: Sure, I'll prepare the access-control and security configuration details for you to review.`,
  },
  {
    id: 'meeting_04_security_review',
    name: 'Meeting 04: Security Review',
    filename: 'meeting_04_security_review.txt',
    description: 'Conflict discovery! Auth0 US data routing vs EU residency requirement.',
    category: 'demo',
    kind: 'transcript',
    content: `[TRANSCRIPT — Project Nexus Security Review] [2024-05-20 3:00 PM | Attendees: Sarah Chen (PM), Dev Rao (Eng Lead), Raj Patel (Security)]

Sarah Chen: Thanks for jumping on, Raj. You flagged something about our auth setup — what's going on?

Raj Patel: Yeah, I was doing a compliance pass ahead of the June 30 launch and found a problem. We locked in "all data must remain in EU region" back in the kickoff, but Auth0's default tenant setup for our plan routes authentication data through US-based infrastructure. That's a direct conflict with our own EU data residency decision.

Dev Rao: Wait, so the Auth0 decision from meeting one might actually violate our own compliance requirement?

Raj Patel: Exactly. I'm not saying we definitely have to rip it out today, but I can't sign off on it as-is. I need to flag this as under review until we either get written confirmation Auth0 can guarantee EU-only data residency on our plan, or we find an alternative.

Sarah Chen: Okay, let's mark the Auth0 authentication decision as under review, not confirmed, until this is resolved. Raj, can you research GDPR-compliant alternatives in case Auth0 can't guarantee this?

Raj Patel: On it. I'll have a recommendation by early next week.`,
  },
  {
    id: 'meeting_05_resolution_call',
    name: 'Meeting 05: Resolution Call',
    filename: 'meeting_05_resolution_call.txt',
    description: 'Conflict resolution: Replaces Auth0 with self-hosted Keycloak in AWS EU.',
    category: 'demo',
    kind: 'transcript',
    content: `[TRANSCRIPT — Project Nexus Resolution Call] [2024-05-27 2:00 PM | Attendees: Sarah Chen (PM), Dev Rao (Eng Lead), Raj Patel (Security), Emily (Backend Engineer)]

Sarah Chen: Raj, you had an update on the Auth0 situation from last week?

Raj Patel: Yes. I confirmed with Auth0's support team — on our current plan, they cannot guarantee EU-only data residency. It would require an enterprise-tier contract we don't have budget for right now.

Dev Rao: So what's the alternative?

Raj Patel: I'd recommend Keycloak. It's open-source, self-hostable, and we can deploy it entirely within our own AWS eu-west-1 region, which satisfies our data residency requirement directly.

Sarah Chen: Okay, let's make it official — we're switching from Auth0 to Keycloak for authentication. This supersedes the Auth0 decision from the kickoff meeting.

Dev Rao: Agreed. That resolves the compliance concern cleanly.

Sarah Chen: Emily, can you own the Keycloak integration work and confirm GDPR compliance once it's deployed?

Emily: Yes, I can take that on. I'll finish the integration and verify GDPR compliance by next month.`,
  },
  {
    id: 'meeting_06_timeline_checkin',
    name: 'Meeting 06: Timeline Check-in (Audio)',
    filename: 'meeting_06_timeline_checkin.mp3',
    description: 'Sample audio file demonstrating Gemini multimodal transcription & pipeline.',
    category: 'demo',
    kind: 'audio',
  },
  {
    id: 'sprint_planning',
    name: 'Sample: Sprint Planning Sync',
    filename: 'sprint_planning.txt',
    description: 'Standard sprint planning meeting with task assignments.',
    category: 'samples',
    kind: 'transcript',
    content: `[TRANSCRIPT — Sprint 12 Planning Sync] [2024-06-03 09:30 AM | Attendees: Sarah Chen (PM), Dev Rao (Tech Lead), Alex Rivera (QA)]

Sarah Chen: Welcome to Sprint 12 planning. Our priority this sprint is completing the API gateway integration and hardening search performance.

Dev Rao: On the API gateway side, I'll take ownership of implementing the OAuth2 bearer token middleware in FastAPI. Target completion by Wednesday.

Alex Rivera: I will write end-to-end regression tests for the search endpoint to ensure sub-100ms response times.

Sarah Chen: Perfect. Let's lock in those action items. We also decided to deprecate legacy V1 endpoints by the end of Q3.`,
  },
];
