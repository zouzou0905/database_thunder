import { ChevronLeft, ChevronRight } from "lucide-react";
import type { FormEvent } from "react";
import { AppleSelect } from "./AppleSelect";

interface PaginationProps {
  page: number;
  totalPages: number;
  pageSize: number;
  pageJump: string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  onPageJumpChange: (value: string) => void;
  onSubmitPageJump: (event: FormEvent) => void;
  pageJumpInputId?: string;
}

export function Pagination({
  page,
  totalPages,
  pageSize,
  pageJump,
  onPageChange,
  onPageSizeChange,
  onPageJumpChange,
  onSubmitPageJump,
  pageJumpInputId = "page-jump-input",
}: PaginationProps) {
  return (
    <div className="pagination">
      <button
        className="button secondary"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        <ChevronLeft size={16} />
        上一页
      </button>
      <span>
        {page} / {totalPages}
      </span>
      <AppleSelect
        compact
        value={String(pageSize)}
        options={[
          { value: "10", label: "10条/页" },
          { value: "50", label: "50条/页" },
          { value: "100", label: "100条/页" },
        ]}
        ariaLabel="每页条数"
        dropUp
        onChange={(value) => onPageSizeChange(Number(value))}
      />
      <form className="page-jump" onSubmit={onSubmitPageJump}>
        <label htmlFor={pageJumpInputId}>跳至</label>
        <input
          id={pageJumpInputId}
          type="number"
          min={1}
          max={totalPages}
          value={pageJump}
          onChange={(event) => onPageJumpChange(event.target.value)}
        />
        <button className="button secondary" type="submit">
          跳转
        </button>
      </form>
      <button
        className="button secondary"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        下一页
        <ChevronRight size={16} />
      </button>
    </div>
  );
}
