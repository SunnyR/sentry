import {IconArrow, IconGraph, IconMenu, IconNumber} from 'sentry/icons';
import {IconGraphArea} from 'sentry/icons/iconGraphArea';
import {IconGraphBar} from 'sentry/icons/iconGraphBar';
import {DisplayType} from 'sentry/views/dashboards/types';

export function getWidgetIcon(displayType: DisplayType) {
  switch (displayType) {
    case DisplayType.TABLE:
      return IconMenu;
    case DisplayType.BIG_NUMBER:
      return IconNumber;
    case DisplayType.BAR:
      return IconGraphBar;
    case DisplayType.TOP_N:
      return IconArrow;
    case DisplayType.AREA:
      return IconGraphArea;
    case DisplayType.LINE:
    default:
      return IconGraph;
  }
}
