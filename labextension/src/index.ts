import { IRenderMime } from '@jupyterlab/rendermime-interfaces';
import { Widget } from '@lumino/widgets';
import { initRefuaWidgets } from './render';

import 'molstar/build/viewer/molstar.css';
import '../style/index.css';

const MIME_TYPE = 'application/vnd.refua+json';

class RefuaRenderer extends Widget implements IRenderMime.IRenderer {
  renderModel(model: IRenderMime.IMimeModel): Promise<void> {
    const data = model.data[MIME_TYPE] as any;
    const html = data?.html || '';

    this.node.innerHTML = html;
    this.node.classList.add('refua-notebook-root');
    initRefuaWidgets(this.node);

    return Promise.resolve();
  }
}

const rendererFactory: IRenderMime.IRendererFactory = {
  safe: true,
  mimeTypes: [MIME_TYPE],
  createRenderer: () => new RefuaRenderer()
};

const extension: IRenderMime.IExtension = {
  id: 'refua-notebook:renderer',
  rendererFactory,
  rank: 0,
  dataType: 'json',
  fileTypes: []
};

export default extension;
