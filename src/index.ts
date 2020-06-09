import 'file-loader?name=index.html!extract-loader!html-loader?interpolate!./index.html';
import './style.scss';
import {LineUp, RemoteDataProvider, IServerData, IOrderedGroup, IRemoteStatistics, IColumnDump, IServerRankingDump, IComputeColumn} from 'lineupjs';

interface IRow {
  d: string;
  a: number;
  cat: string;
  cat2: string;
}

function toColumn(desc: IColumnDump) {
  return desc.desc.split('@')[1];
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
    return this.post(`/api/ranking/sort`, ranking);
  }

  view(indices: number[]): Promise<IRow[]> {
    if (indices.length === 1) {
      return fetch(`/api/row/${encodeURIComponent(indices[0].toString())}`).then((r) => r.json()).then((r) => [r]);
    }
    if (indices.length > 100) {
      return this.post(`/api/row/`, indices);
    }
    return fetch(`/api/row/?ids=${encodeURIComponent(indices.join(','))}`).then((r) => r.json());
  }

  mappingSample(column: IColumnDump): Promise<number[]> {
    return this.post(`/api/column/${toColumn(column)}/mappingSample`, column);
  }

  search(search: string | RegExp, column: IColumnDump): Promise<number[]> {
    return fetch(`/api/column/${toColumn(column)}/search?query=${encodeURIComponent(search.toString())}`).then((r) => r.json());
  }

  computeDataStats(columns: IComputeColumn[]): Promise<IRemoteStatistics[]> {
    return this.post(`/api/stats`, columns);
  }

  computeRankingStats(ranking: IServerRankingDump, columns: IComputeColumn[]): Promise<IRemoteStatistics[]> {
    return this.post(`/api/ranking/stats`, {ranking, columns});
  }

  computeGroupStats(ranking: IServerRankingDump, group: string, columns: IComputeColumn[]): Promise<IRemoteStatistics[]> {
    return this.post(`/api/ranking/group/${group}/stats`, {ranking, columns});
  }
}


Promise.all([
  fetch('/api/desc').then((r) => r.json()),
  fetch('/api/count').then((r) => r.json())
]).then(([desc, count]: [any[], number]) => {
  const provider = new RemoteDataProvider(new Server(count), desc, {});
  provider.deriveDefault();

  return new LineUp(document.body, provider, {});
});
