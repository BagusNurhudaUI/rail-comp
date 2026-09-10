import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/** Ambil data sekali, atau ulangi saat `deps` berubah.
 *
 *  Status muat diturunkan dari perbandingan kunci permintaan dengan kunci
 *  hasil terakhir, bukan dari `setState` di badan efek. Selain menghindari
 *  render berantai, ini juga membuat perpindahan `deps` langsung terbaca
 *  sebagai "sedang memuat" tanpa satu frame data basi.
 */
export function useFetch(fetcher, deps = [], { skip = false } = {}) {
  const [nonce, setNonce] = useState(0);
  const key = useMemo(() => JSON.stringify([deps, nonce]), [deps, nonce]);

  const [result, setResult] = useState({ key: null, data: null, error: null });

  // Fungsi pengambil data biasanya berupa closure baru setiap render, jadi ia
  // disimpan di ref agar tidak ikut memicu efek. Ref diperbarui di dalam efek
  // (bukan saat render) dan dideklarasikan lebih dulu supaya sudah mutakhir
  // ketika efek pengambil data di bawahnya berjalan.
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const refetch = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    if (skip) return undefined;

    let active = true;

    fetcherRef
      .current()
      .then((data) => active && setResult({ key, data, error: null }))
      .catch((exception) => active && setResult({ key, data: null, error: exception.message }));

    return () => {
      active = false;
    };
  }, [key, skip]);

  return {
    data: result.data,
    error: result.error,
    loading: !skip && result.key !== key,
    refetch,
  };
}

/** Tabel berhalaman dengan filter.
 *
 *  Perubahan filter selalu mengembalikan halaman ke 1 — tanpa itu pengguna
 *  bisa terdampar di halaman kosong setelah hasil menyusut.
 */
export function usePagedQuery(fetcher, initialFilters = {}, initialPageSize = 25) {
  const [filters, setFilters] = useState(initialFilters);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [nonce, setNonce] = useState(0);

  const key = useMemo(
    () => JSON.stringify({ filters, page, pageSize, nonce }),
    [filters, page, pageSize, nonce],
  );

  const [result, setResult] = useState({ key: null, items: [], total: 0, error: null });

  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    let active = true;

    fetcherRef
      .current({ ...filters, page, page_size: pageSize })
      .then(
        (data) =>
          active &&
          setResult({ key, items: data.items || [], total: data.total || 0, error: null }),
      )
      .catch(
        (exception) =>
          active && setResult({ key, items: [], total: 0, error: exception.message }),
      );

    return () => {
      active = false;
    };
    // filters/page/pageSize sudah terangkum di `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const setFilter = useCallback((name, value) => {
    setPage(1);
    setFilters((previous) => ({ ...previous, [name]: value }));
  }, []);

  return {
    items: result.items,
    total: result.total,
    error: result.error,
    loading: result.key !== key,
    filters,
    setFilter,
    setFilters,
    page,
    setPage,
    pageSize,
    setPageSize,
    reload: useCallback(() => setNonce((value) => value + 1), []),
  };
}
