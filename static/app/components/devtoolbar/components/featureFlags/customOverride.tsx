import {useContext, useState} from 'react';
import {css} from '@emotion/react';

import {Input} from 'sentry/components/core/input';
import {Switch} from 'sentry/components/core/switch';
import {AnalyticsContext} from 'sentry/components/devtoolbar/components/analyticsProvider';
import useConfiguration from 'sentry/components/devtoolbar/hooks/useConfiguration';
import {resetButtonCss} from 'sentry/components/devtoolbar/styles/reset';
import {IconAdd} from 'sentry/icons';

import {useFeatureFlagsContext} from './featureFlagsContext';

export default function CustomOverride({
  setComponentActive,
}: {
  setComponentActive: (value: boolean) => void;
}) {
  const {eventName, eventKey} = useContext(AnalyticsContext);
  const {trackAnalytics} = useConfiguration();
  const {setOverride} = useFeatureFlagsContext();

  const [name, setName] = useState('');
  const [isActive, setIsActive] = useState(false);

  return (
    <form
      css={css`
        display: grid;
        grid-template-columns: auto max-content max-content;
        align-items: center;
        justify-items: space-between;
        gap: var(--space100);
      `}
      onSubmit={e => {
        e.preventDefault();
        setOverride(name, isActive);
        setComponentActive(false);
        setName('');
        setIsActive(false);
        trackAnalytics?.({
          eventKey: eventKey + '.created',
          eventName: eventName + ' created',
        });
      }}
    >
      <Input
        size="xs"
        placeholder="Flag name to override"
        value={name}
        onChange={e => setName(e.target.value.toLowerCase())}
      />
      <Switch
        size="lg"
        checked={isActive}
        onChange={() => {
          setIsActive(!isActive);
        }}
        css={css`
          background: white;
        `}
      />
      <button
        type="submit"
        css={[
          resetButtonCss,
          css`
            width: 28px;
          `,
        ]}
        disabled={!name.length}
      >
        <IconAdd />
      </button>
    </form>
  );
}
