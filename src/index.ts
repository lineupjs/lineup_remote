import 'file-loader?name=index.html!extract-loader!html-loader?interpolate!./index.html';
import './style.scss';
import {LineUp, RemoteDataProvider, IServerData, IOrderedGroup, IRemoteStatistics, IColumnDump, IServerRankingDump} from 'lineupjs';

interface IRow {
  d: string;
  a: number;
  cat: string;
  cat2: string;
}

class Server implements IServerData {
  constructor(public readonly totalNumberOfRows: number) {

  }

  sort(ranking: IServerRankingDump): Promise<{groups: IOrderedGroup[]; maxDataIndex: number;}> {
    throw new Error('Method not implemented.');
  }

  view(indices: number[]): Promise<IRow[]> {
    const url = new URL('/api/row');
    url.searchParams.set('ids', indices.join(','));
    return fetch(url.href).then((r) => r.json());
  }

  mappingSample(column: IColumnDump): Promise<number[]> {
    throw new Error('Method not implemented.');
  }

  search(search: string | RegExp, column: IColumnDump): Promise<number[]> {
    throw new Error('Method not implemented.');
  }

  computeDataStats(columns: IColumnDump[]): Promise<IRemoteStatistics[]> {
    throw new Error('Method not implemented.');
  }
  computeRankingStats(ranking: IServerRankingDump, columns: IColumnDump[]): Promise<IRemoteStatistics[]> {
    throw new Error('Method not implemented.');
  }
  computeGroupStats(ranking: IServerRankingDump, group: string, columns: IColumnDump[]): Promise<IRemoteStatistics[]> {
    throw new Error('Method not implemented.');
  }


}

const desc = [{
    label: 'D',
    type: 'string',
    column: 'd'
  },
  {
    label: 'A',
    type: 'number',
    column: 'a',
    domain: [0, 10]
  },
  {
    label: 'Cat',
    type: 'categorical',
    column: 'cat',
    categories: ['c1', 'c2', 'c3']
  },
  {
    label: 'Cat Label',
    type: 'categorical',
    column: 'cat2',
    categories: [{
      name: 'a1',
      label: 'A1',
      color: 'green'
    }, {
      name: 'a2',
      label: 'A2',
      color: 'blue'
    }]
  }
];

fetch('/api/row/count').then((r) => r.json()).then((count: number) => {
  const provider = new RemoteDataProvider(new Server(count), desc, {});

  const lineup = new LineUp(document.body, provider, {});
});
