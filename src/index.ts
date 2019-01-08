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

  private post(url: string, body: object) {
    return fetch(url, {
      method: 'POST',
      body: JSON.stringify(body, null, 2),
      headers: {
        'Content-Type': 'application/json'
      }
    }).then((r) => r.json());
  }

  sort(ranking: IServerRankingDump): Promise<{groups: IOrderedGroup[]; maxDataIndex: number;}> {
    // fix indices to typed array
    return this.post(`/api/sort`, ranking);
  }

  view(indices: number[]): Promise<IRow[]> {
    const url = new URL('/api/row');
    url.searchParams.set('ids', indices.join(','));
    return fetch(url.href).then((r) => r.json());
  }

  mappingSample(column: IColumnDump): Promise<number[]> {
    return this.post(`/api/column/${column.id}/mappingSample`, column);
  }

  search(search: string | RegExp, column: IColumnDump): Promise<number[]> {
    const url = new URL(`/api/column/${column.id}`);
    url.searchParams.set('query', search.toString());
    return fetch(url.href).then((r) => r.json());
  }

  computeDataStats(columns: IColumnDump[]): Promise<IRemoteStatistics[]> {
    return this.post(`/api/stats`, columns);
  }

  computeRankingStats(ranking: IServerRankingDump, columns: IColumnDump[]): Promise<IRemoteStatistics[]> {
    return this.post(`/api/ranking/stats`, {ranking, columns});
  }

  computeGroupStats(ranking: IServerRankingDump, group: string, columns: IColumnDump[]): Promise<IRemoteStatistics[]> {
    return this.post(`/api/ranking/group/${group}/stats`, {ranking, columns});
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
