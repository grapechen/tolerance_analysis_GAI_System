/**
 * step_viewer.js - Three.js STEP PMI 3D 查看器模組
 * ========================================================
 * 負責處理STEP幾何三角化、PMI高亮、leader lines 渲染等
 */

const StepViewer = (() => {
    let renderer, scene, camera, controls;
    let currentSession = null;
    let geometryMeshes = {};     // face_id_str -> THREE.Mesh
    let pmiLineMeshes  = {};     // row_index -> THREE.LineSegments
    let baseGeometryMesh = null; // 整體模型基礎幾何（灰色）

    const COLORS = {
        default:     0xccddff,   // 淺藍
        datum:       0x00DA26,   // 綠色
        interactive: 0xA121F0,   // 紫色
        individual:  0xFFA500,   // 橘色
        hover:       0xFFFF00,   // 黃色
    };

    /**
     * 初始化 Three.js 場景
     */
    function init(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`❌ Canvas element not found: ${canvasId}`);
            return false;
        }

        // 建立 renderer
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(canvas.clientWidth, canvas.clientHeight);
        renderer.setClearColor(0xfafafa);
        canvas.appendChild(renderer.domElement);

        // 建立 scene
        scene = new THREE.Scene();

        // 建立 camera
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 10000);
        camera.position.set(0, 0, 100);

        // 建立 OrbitControls
        controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.enableZoom = true;

        // 加入基礎光源
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
        directionalLight.position.set(100, 100, 100);
        scene.add(directionalLight);

        // 啟動動畫迴圈
        animate();

        // 處理視窗縮放
        window.addEventListener('resize', onWindowResize);

        console.log('✅ StepViewer 初始化完成');
        return true;
    }

    /**
     * 載入全部幾何（低精度概覽），作為半透明底模
     */
    function loadAllGeometry(sessionId, deflection = 0.3) {
        if (!sessionId) {
            console.error('❌ loadAllGeometry: 缺少 sessionId');
            return;
        }

        currentSession = sessionId;
        console.log(`⏳ 載入 session ${sessionId} 的所有幾何...`);

        fetch(`/api/step/geometry?session_id=${sessionId}&face_ids=*&deflection=${deflection}`)
            .then(r => r.json())
            .then(data => {
                if (!data.ok) {
                    console.error('❌ 幾何載入失敗:', data.error);
                    return;
                }

                if (data.geometry && data.geometry.vertices) {
                    if (baseGeometryMesh) {
                        scene.remove(baseGeometryMesh);
                    }
                    const { vertices, faces, normals } = data.geometry;
                    const geom = new THREE.BufferGeometry();
                    geom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(vertices.flat()), 3));
                    if (normals && normals.length > 0) {
                        geom.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(normals.flat()), 3));
                    }
                    geom.setIndex(new THREE.BufferAttribute(new Uint32Array(faces.flat()), 1));
                    geom.computeBoundingSphere();

                    const mat = new THREE.MeshStandardMaterial({
                        color: 0xcccccc,
                        transparent: true,
                        opacity: 0.3,   // 半透明底模
                        metalness: 0.1,
                        roughness: 0.8
                    });

                    baseGeometryMesh = new THREE.Mesh(geom, mat);
                    scene.add(baseGeometryMesh);

                    console.log('✅ 基礎幾何 透明底模建立完成');
                    
                    // 等待底模讀取完後置中相機
                    focusOnGeometry();
                } else {
                    console.warn('⚠️ 基礎幾何點面資料為空');
                }
            })
            .catch(err => console.error('❌ 幾何查詢錯誤:', err));
    }

    /**
     * 高亮指定的 PMI（拉取幾何+leader lines）
     */
    function highlightPmiRow(rowIndex) {
        if (!currentSession) {
            console.error('❌ highlightPmiRow: 沒有活躍的 session');
            return;
        }

        console.log(`🔍 高亮 PMI row ${rowIndex}...`);

        fetch(`/api/step/highlight`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession,
                row_index: rowIndex
            })
        })
            .then(r => r.json())
            .then(data => {
                if (!data.ok) {
                    console.error('❌ 高亮失敗:', data.error);
                    return;
                }

                // 渲染 face 幾何
                if (data.face_geometry && data.face_geometry.vertices) {
                    renderFaceGeometry(data.face_geometry, data.highlight_color, rowIndex);
                }

                // 渲染 leader lines
                if (data.leader_lines && data.leader_lines.length > 0) {
                    renderLeaderLines(data.leader_lines, rowIndex);
                }

                console.log(`✅ PMI ${rowIndex} 高亮完成`);
                // 批次選擇時不頻繁移動視角，讓用戶自己轉動
                // focusOnGeometry();
            })
            .catch(err => console.error('❌ 高亮查詢錯誤:', err));
    }

    /**
     * 同步當下所有勾選的 PMI 項目
     */
    function syncHighlights(indices) {
        // 第一步：移除不在清單內的 meshes
        Object.keys(geometryMeshes).forEach(key => {
            const idx = parseInt(key.replace('face_', ''));
            if (!indices.includes(idx)) {
                scene.remove(geometryMeshes[key]);
                if (geometryMeshes[key].geometry) geometryMeshes[key].geometry.dispose();
                if (geometryMeshes[key].material) geometryMeshes[key].material.dispose();
                delete geometryMeshes[key];
            }
        });

        Object.keys(pmiLineMeshes).forEach(key => {
            const idx = parseInt(key.replace('lines_', ''));
            if (!indices.includes(idx)) {
                scene.remove(pmiLineMeshes[key]);
                if (pmiLineMeshes[key].geometry) pmiLineMeshes[key].geometry.dispose();
                if (pmiLineMeshes[key].material) pmiLineMeshes[key].material.dispose();
                delete pmiLineMeshes[key];
            }
        });

        // 第二步：新增還未載入的 highlight
        indices.forEach(idx => {
            if (!geometryMeshes[`face_${idx}`] && !pmiLineMeshes[`lines_${idx}`]) {
                highlightPmiRow(idx);
            }
        });
    }

    /**
     * 渲染 face 幾何
     */
    function renderFaceGeometry(geomData, colorHex, rowIndex) {
        const { vertices, faces, normals } = geomData;

        if (!vertices || !faces) {
            console.warn('⚠️ 幾何數據不完整');
            return;
        }

        // 建立 BufferGeometry
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(
            new Float32Array(vertices.flat()), 3
        ));
        if (normals && normals.length > 0) {
            geometry.setAttribute('normal', new THREE.BufferAttribute(
                new Float32Array(normals.flat()), 3
            ));
        }
        geometry.setIndex(new THREE.BufferAttribute(
            new Uint32Array(faces.flat()), 1
        ));
        geometry.computeBoundingSphere();

        // 建立材質
        const material = new THREE.MeshStandardMaterial({
            color: colorHex,
            metalness: 0.3,
            roughness: 0.7
        });

        // 建立 mesh
        const mesh = new THREE.Mesh(geometry, material);
        scene.add(mesh);

        // 快取（以便後續切換顏色或隱藏）
        const key = `face_${rowIndex}`;
        if (geometryMeshes[key]) {
            scene.remove(geometryMeshes[key]);
        }
        geometryMeshes[key] = mesh;
    }

    /**
     * 渲染 leader lines（標註線）
     */
    function renderLeaderLines(linesData, rowIndex) {
        if (!linesData || linesData.length === 0) {
            return;
        }

        const points = [];
        linesData.forEach(line => {
            // 每條 line 是 [[x1,y1,z1], [x2,y2,z2]]
            points.push(new THREE.Vector3(...line[0]));
            points.push(new THREE.Vector3(...line[1]));
        });

        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const material = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 2 });
        const lines = new THREE.LineSegments(geometry, material);
        scene.add(lines);

        const key = `lines_${rowIndex}`;
        if (pmiLineMeshes[key]) {
            scene.remove(pmiLineMeshes[key]);
        }
        pmiLineMeshes[key] = lines;
    }

    /**
     * 清空所有高亮
     */
    function clearHighlights() {
        Object.values(geometryMeshes).forEach(mesh => scene.remove(mesh));
        Object.values(pmiLineMeshes).forEach(lines => scene.remove(lines));
        geometryMeshes = {};
        pmiLineMeshes = {};
        console.log('✅ 清空高亮');
    }

    /**
     * 調整相機聚焦在幾何上
     */
    function focusOnGeometry() {
        let boundingBox = new THREE.Box3();
        scene.traverse(obj => {
            if (obj.isMesh) {
                boundingBox.expandByObject(obj);
            }
        });

        if (boundingBox.isEmpty()) {
            console.warn('⚠️ 場景為空，無法聚焦');
            return;
        }

        const center = boundingBox.getCenter(new THREE.Vector3());
        const size = boundingBox.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = camera.fov * (Math.PI / 180); // 轉換為弧度
        let cameraZ = maxDim / 2 / Math.tan(fov / 2);

        camera.position.copy(center);
        camera.position.z += cameraZ * 1.2;
        camera.lookAt(center);
        controls.target.copy(center);
        controls.update();
    }

    /**
     * 釋放資源
     */
    function dispose() {
        if (renderer) {
            renderer.dispose();
        }
        scene.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
        window.removeEventListener('resize', onWindowResize);
        console.log('✅ StepViewer 資源已釋放');
    }

    /**
     * 窗口縮放處理
     */
    function onWindowResize() {
        const canvas = renderer.domElement;
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
    }

    /**
     * 渲染迴圈
     */
    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }

    // 暴露公共 API
    return {
        init,
        loadAllGeometry,
        highlightPmiRow,
        syncHighlights,
        clearHighlights,
        focusOnGeometry,
        dispose
    };
})();
