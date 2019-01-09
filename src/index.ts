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


Promise.all([
  fetch('/api/desc').then((r) => r.json()),
  fetch('/api/count').then((r) => r.json())
]).then(([desc, count]: [any[], number]) => {
  const provider = new RemoteDataProvider(new Server(count), desc, {});

  return new LineUp(document.body, provider, {});
});
