import {useEffect} from 'react';
import {css} from '@emotion/react';
import styled from '@emotion/styled';

import {useNavContext} from 'sentry/views/nav/context';
import MobileTopbar from 'sentry/views/nav/mobileTopbar';
import {SecondaryNavContent} from 'sentry/views/nav/secondary/secondaryNavContent';
import {Sidebar} from 'sentry/views/nav/sidebar';
import {
  NavigationTourProvider,
  useStackedNavigationTour,
} from 'sentry/views/nav/tour/tour';
import {NavLayout} from 'sentry/views/nav/types';

function NavContent() {
  const {layout, navParentRef} = useNavContext();
  const {currentStepId, endTour} = useStackedNavigationTour();
  const tourIsActive = currentStepId !== null;

  // The tour only works with the sidebar layout, so if we change to the mobile
  // layout in the middle of the tour, it needs to end.
  useEffect(() => {
    if (tourIsActive && layout === NavLayout.MOBILE) {
      endTour();
    }
  }, [endTour, layout, tourIsActive]);

  return (
    <NavContainer
      ref={navParentRef}
      tourIsActive={tourIsActive}
      isMobile={layout === NavLayout.MOBILE}
    >
      {layout === NavLayout.SIDEBAR ? <Sidebar /> : <MobileTopbar />}
      <SecondaryNavContent />
    </NavContainer>
  );
}

function Nav() {
  return (
    <NavigationTourProvider>
      <NavContent />
    </NavigationTourProvider>
  );
}

const NavContainer = styled('div')<{isMobile: boolean; tourIsActive: boolean}>`
  display: flex;
  user-select: none;

  ${p =>
    !p.tourIsActive &&
    css`
      position: sticky;
      top: 0;
      z-index: ${p.theme.zIndex.sidebarPanel};
    `}

  ${p =>
    !p.isMobile &&
    css`
      bottom: 0;
      height: 100vh;
      height: 100dvh;
    `}
`;

export default Nav;
