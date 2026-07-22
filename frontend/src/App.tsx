import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppProviders } from './state/app';
import { Shell } from './components/Shell';

import { HomeView } from './views/Home';
import { MeetingsView } from './views/Meetings';
import { DecisionsView } from './views/Decisions';
import { ActionItemsView } from './views/ActionItems';
import { AskView } from './views/Ask';
import { MapView } from './views/Map';
import { AddMeetingView } from './views/AddMeeting';
import { SettingsView } from './views/Settings';

export const App: React.FC = () => (
  <AppProviders>
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<HomeView />} />
          <Route path="/meetings" element={<MeetingsView />} />
          <Route path="/decisions" element={<DecisionsView />} />
          <Route path="/tasks" element={<ActionItemsView />} />
          <Route path="/ask" element={<AskView />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/add" element={<AddMeetingView />} />
          <Route path="/settings" element={<SettingsView />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  </AppProviders>
);

export default App;
