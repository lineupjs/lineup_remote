import 'file-loader?name=index.html!extract-loader!html-loader?interpolate!./index.html';
import './style.scss';
import {LineUp, RemoteDataProvider, IServerData} from 'lineupjs';

class Server implements IServerData {
  view(indices: number[]): Promise<any[]> {
    throw new Error("Method not implemented.");
  }

  mappingSample(column: any): Promise<number[]> {
    throw new Error("Method not implemented.");
  }

  search(search: string | RegExp, column: any): Promise<number[]> {
    throw new Error("Method not implemented.");
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
    'domain': [0, 10]
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
const provider = new RemoteDataProvider(new Server(), desc, {});

const lineup = new LineUp(document.body, provider, {});
